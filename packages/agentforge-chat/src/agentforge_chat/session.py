"""`ChatSession` — stateful conversation wrapper around `Agent`
(feat-020).

Lifecycle per turn (`send` / `stream`):

  1. Acquire per-session lock.
  2. Check idempotency cache.
  3. Build user `ChatTurn` and run input guardrails.
  4. Append user turn.
  5. Load + truncate prior history.
  6. Build the agent task as a serialised transcript.
  7. `agent.run(task)`.
  8. Run output guardrails.
  9. Append assistant + tool turns.
 10. Aggregate per-turn / per-session cost.
 11. Release lock; return `ChatResponse`.

Cancellation in v0.2 is pre-LLM only (between history-load and
agent.run). Mid-LLM cancellation needs the same strategy-level
streaming work documented in feat-020 §10 deferrals.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import uuid4

from agentforge.agent import Agent
from agentforge_core.contracts.chat import ChatHistoryStore, HistoryTruncationStrategy
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.production.exceptions import (
    BudgetExceeded,
    GuardrailViolation,
)
from agentforge_core.values.chat import ChatChunk, ChatResponse, ChatTurn, StreamingEvent

from agentforge_chat._idempotency import IdempotencyCache
from agentforge_chat._locks import (
    SessionLockFactory,
    default_session_lock_factory,
)
from agentforge_chat._segment import segment_for_stream
from agentforge_chat.history import InMemoryChatHistory
from agentforge_chat.truncation import SlidingWindow

OnTurnHook = Callable[[ChatTurn], None]


class ChatSession:
    """Wrap a one-shot `Agent` into a multi-turn chat session."""

    def __init__(
        self,
        agent: Agent,
        *,
        session_id: str | None = None,
        history_store: ChatHistoryStore | None = None,
        system_prompt: str | None = None,
        truncation: HistoryTruncationStrategy | None = None,
        owner: str | None = None,
        per_turn_budget_usd: float | None = None,
        per_session_budget_usd: float | None = None,
        idempotency_window_s: float = 60.0,
        on_turn: OnTurnHook | None = None,
        session_lock_factory: SessionLockFactory | None = None,
    ) -> None:
        self._agent = agent
        self._session_id = session_id if session_id is not None else uuid4().hex
        self._history: ChatHistoryStore = (
            history_store if history_store is not None else InMemoryChatHistory()
        )
        self._system_prompt = system_prompt
        self._truncation: HistoryTruncationStrategy = (
            truncation if truncation is not None else SlidingWindow(50)
        )
        self._owner = owner
        self._per_turn_budget = per_turn_budget_usd
        self._per_session_budget = per_session_budget_usd
        self._on_turn = on_turn
        factory = session_lock_factory or default_session_lock_factory
        self._lock = factory(self._session_id)
        self._idempotency: IdempotencyCache[ChatResponse] = IdempotencyCache(
            ttl_s=idempotency_window_s
        )
        self._total_cost = 0.0
        self._turn_count = 0
        self._closed = False

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost

    @property
    def turn_count(self) -> int:
        return self._turn_count

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send(
        self,
        message: str,
        *,
        idempotency_key: str | None = None,
        cancellation: asyncio.Event | None = None,
    ) -> ChatResponse:
        """Send one user message and await a buffered response."""
        async with self._lock:
            cached = self._check_cache(idempotency_key)
            if cached is not None:
                return cached
            response, _ = await self._run_turn(message, cancellation=cancellation)
            self._stash_cache(idempotency_key, response)
            return response

    async def stream(
        self,
        message: str,
        *,
        idempotency_key: str | None = None,
        cancellation: asyncio.Event | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Send one user message and stream the response back as chunks.

        v0.2 uses buffer-then-stream: the agent runs to completion,
        then the assistant turn is emitted as a sequence of text
        chunks (sentence-segmented) followed by a `done` chunk. Real
        per-token streaming becomes a no-API-break enhancement when
        the strategy ABC grows a `stream()` method.
        """
        return self._stream_impl(message, idempotency_key, cancellation)

    async def history(
        self,
        *,
        limit: int | None = None,
        roles: list[str] | None = None,
    ) -> list[ChatTurn]:
        return await self._history.load(self._session_id, limit=limit, roles=roles)

    async def reset(self) -> None:
        await self._history.delete_session(self._session_id)
        self._total_cost = 0.0
        self._turn_count = 0

    async def close(self) -> None:
        if self._closed:
            return
        await self._history.close()
        self._closed = True

    # ------------------------------------------------------------------
    # Implementation helpers
    # ------------------------------------------------------------------

    def _check_cache(self, key: str | None) -> ChatResponse | None:
        if key is None:
            return None
        return self._idempotency.get(self._session_id, key)

    def _stash_cache(self, key: str | None, response: ChatResponse) -> None:
        if key is None:
            return
        self._idempotency.put(self._session_id, key, response)

    async def _run_turn(
        self,
        message: str,
        *,
        cancellation: asyncio.Event | None,
    ) -> tuple[ChatResponse, ChatTurn]:
        ctx = self._guard_context()
        validated_msg = await self._agent._guardrails.check_input(message, ctx)
        user_turn = await self._build_user_turn(validated_msg)
        if cancellation is not None and cancellation.is_set():
            raise asyncio.CancelledError("chat turn cancelled before agent.run")
        task = await self._compose_task(user_turn)
        start = time.monotonic()
        result = await self._agent.run(task)
        duration_ms = int((time.monotonic() - start) * 1000)
        validated_out = await self._agent._guardrails.check_output(self._extract_text(result), ctx)
        assistant_turn = await self._persist_assistant(validated_out, result, duration_ms)
        self._enforce_budgets(result.cost_usd)
        response = ChatResponse(
            content=validated_out,
            turn_id=assistant_turn.id,
            run_id=result.run_id,
            tool_calls=(),
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            duration_ms=duration_ms,
            finish_reason=str(result.finish_reason),
        )
        return response, assistant_turn

    def _guard_context(self) -> dict[str, Any]:
        return {
            "session_id": self._session_id,
            "owner": self._owner or "anonymous",
            "project": "chat",
        }

    async def _build_user_turn(self, content: str) -> ChatTurn:
        turn = ChatTurn(
            id=uuid4().hex,
            session_id=self._session_id,
            role="user",
            content=content,
        )
        await self._history.append(turn)
        if self._on_turn is not None:
            self._on_turn(turn)
        return turn

    async def _compose_task(self, user_turn: ChatTurn) -> str:
        prior = await self._history.load(self._session_id, limit=None)
        # Drop the just-appended user turn — it's added as the final
        # line below.
        prior_without_current = [t for t in prior if t.id != user_turn.id]
        kept = await self._truncation.select(prior_without_current, user_turn.content, {})
        lines: list[str] = []
        prompt = self._system_prompt or ""
        if prompt:
            lines.append(prompt)
        lines.extend(f"{t.role}: {t.content}" for t in kept)
        lines.append(f"user: {user_turn.content}")
        return "\n\n".join(lines)

    def _extract_text(self, result: Any) -> str:
        output = result.output
        if isinstance(output, str):
            return output
        return str(output)

    async def _persist_assistant(
        self,
        text: str,
        result: Any,
        duration_ms: int,
    ) -> ChatTurn:
        del duration_ms
        turn = ChatTurn(
            id=uuid4().hex,
            session_id=self._session_id,
            role="assistant",
            content=text,
            run_id=result.run_id,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
        )
        await self._history.append(turn)
        if self._on_turn is not None:
            self._on_turn(turn)
        self._total_cost += result.cost_usd
        self._turn_count += 1
        await self._history.update_session_metadata(
            self._session_id,
            {"owner": self._owner, "total_cost_usd": self._total_cost},
        )
        return turn

    def _enforce_budgets(self, turn_cost: float) -> None:
        if self._per_turn_budget is not None and turn_cost > self._per_turn_budget:
            raise BudgetExceeded(
                f"chat turn cost ${turn_cost:.4f} exceeds per-turn budget "
                f"${self._per_turn_budget:.4f}"
            )
        if self._per_session_budget is not None and self._total_cost > self._per_session_budget:
            raise BudgetExceeded(
                f"chat session total ${self._total_cost:.4f} exceeds per-session "
                f"budget ${self._per_session_budget:.4f}"
            )

    def _strategy_overrides_stream(self) -> bool:
        """True when the agent's strategy defines its own `stream()`.

        Distinguishes "real per-token streaming" from the default
        ABC behaviour (which just wraps `run()` + emits one `done`).
        Real per-token strategies override `stream()` to yield text /
        tool-call events as the LLM emits them. v0.2 falls back to
        buffer-then-stream when the override isn't there so v0.1
        callers get the same wire shape they had before.
        """
        return type(self._agent._strategy).stream is not ReasoningStrategy.stream

    async def _stream_impl(
        self,
        message: str,
        idempotency_key: str | None,
        cancellation: asyncio.Event | None,
    ) -> AsyncIterator[ChatChunk]:
        async with self._lock:
            cached = self._check_cache(idempotency_key)
            if cached is not None:
                async for chunk in self._chunks_for(cached):
                    yield chunk
                return
            if self._strategy_overrides_stream():
                try:
                    async for chunk in self._stream_per_token(message, cancellation=cancellation):
                        yield chunk
                    return  # noqa: TRY300 — return in try is the explicit happy-path exit
                except (BudgetExceeded, GuardrailViolation, asyncio.CancelledError) as exc:
                    yield ChatChunk(
                        kind="error",
                        turn_id=uuid4().hex,
                        content={"reason": type(exc).__name__, "message": str(exc)},
                    )
                    return
            try:
                response, _ = await self._run_turn(message, cancellation=cancellation)
            except (BudgetExceeded, GuardrailViolation, asyncio.CancelledError) as exc:
                yield ChatChunk(
                    kind="error",
                    turn_id=uuid4().hex,
                    content={"reason": type(exc).__name__, "message": str(exc)},
                )
                return
            self._stash_cache(idempotency_key, response)
            async for chunk in self._chunks_for(response):
                yield chunk

    async def _stream_per_token(
        self,
        message: str,
        *,
        cancellation: asyncio.Event | None,
    ) -> AsyncIterator[ChatChunk]:
        """Drive the agent via `agent.stream(task)` and forward every
        `StreamingEvent` as a `ChatChunk`. Persists the user + final
        assistant turns and updates per-session budgets the same way
        `_run_turn` does.
        """
        ctx = self._guard_context()
        validated_msg = await self._agent._guardrails.check_input(message, ctx)
        user_turn = await self._build_user_turn(validated_msg)
        if cancellation is not None and cancellation.is_set():
            raise asyncio.CancelledError("chat turn cancelled before agent.stream")
        task = await self._compose_task(user_turn)
        assistant_turn_id = uuid4().hex
        cumulative = ""
        run_summary: dict[str, Any] | None = None
        start = time.monotonic()
        async for event in self._agent.stream(task):
            chunk = self._chunk_from_event(event, assistant_turn_id)
            if event.kind == "done":
                if isinstance(event.content, dict):
                    run_summary = event.content
                break
            if event.kind == "text" and isinstance(event.content, str):
                cumulative += event.content
            yield chunk
        duration_ms = int((time.monotonic() - start) * 1000)
        if run_summary is None:
            run_summary = {
                "output": cumulative,
                "run_id": uuid4().hex,
                "cost_usd": 0.0,
                "tokens_in": 0,
                "tokens_out": 0,
                "finish_reason": "completed",
                "duration_ms": duration_ms,
            }
        final_text = (
            str(run_summary.get("output", cumulative))
            if isinstance(run_summary.get("output"), str)
            else cumulative
        )
        validated_out = await self._agent._guardrails.check_output(final_text, ctx)
        assistant_turn = ChatTurn(
            id=assistant_turn_id,
            session_id=self._session_id,
            role="assistant",
            content=validated_out,
            run_id=str(run_summary.get("run_id", "")),
            tokens_in=int(run_summary.get("tokens_in", 0) or 0),
            tokens_out=int(run_summary.get("tokens_out", 0) or 0),
            cost_usd=float(run_summary.get("cost_usd", 0.0) or 0.0),
        )
        await self._history.append(assistant_turn)
        if self._on_turn is not None:
            self._on_turn(assistant_turn)
        self._total_cost += float(run_summary.get("cost_usd", 0.0) or 0.0)
        self._turn_count += 1
        await self._history.update_session_metadata(
            self._session_id,
            {"owner": self._owner, "total_cost_usd": self._total_cost},
        )
        self._enforce_budgets(float(run_summary.get("cost_usd", 0.0) or 0.0))
        yield ChatChunk(
            kind="done",
            turn_id=assistant_turn_id,
            content={
                "run_id": str(run_summary.get("run_id", "")),
                "cost_usd": float(run_summary.get("cost_usd", 0.0) or 0.0),
                "tokens_in": int(run_summary.get("tokens_in", 0) or 0),
                "tokens_out": int(run_summary.get("tokens_out", 0) or 0),
            },
        )

    def _chunk_from_event(self, event: StreamingEvent, turn_id: str) -> ChatChunk:
        return ChatChunk(
            kind=event.kind,
            content=event.content,
            cumulative_text=event.cumulative_text,
            turn_id=turn_id,
            metadata=dict(event.metadata),
        )

    async def _chunks_for(self, response: ChatResponse) -> AsyncIterator[ChatChunk]:
        cumulative = ""
        for piece in segment_for_stream(response.content):
            cumulative += piece
            yield ChatChunk(
                kind="text",
                content=piece,
                cumulative_text=cumulative,
                turn_id=response.turn_id,
            )
        yield ChatChunk(
            kind="done",
            turn_id=response.turn_id,
            content={
                "run_id": response.run_id,
                "cost_usd": response.cost_usd,
                "tokens_in": response.tokens_in,
                "tokens_out": response.tokens_out,
            },
        )


__all__ = ["ChatSession"]
