"""Truncation strategies (feat-020).

Four built-ins ship in v0.2:

- `SlidingWindow(max_turns=N)` — keep the last N turns.
- `TokenBudget(max_tokens=N)` — keep as many recent turns as fit
  under N tokens (approximate, using a 4-chars-per-token heuristic
  in v0.2; provider-aware tokenisation is a follow-up).
- `SummariseOldest(threshold_turns=N, summariser=cb)` — keep the
  last N turns verbatim; everything older condenses to a single
  ``system`` turn via the supplied summariser callback.
- `Hybrid(*strategies)` — pipe input through each strategy in
  order; later strategies see the previous strategy's output.

Each respects the conformance invariants documented in
`agentforge_core.contracts.chat.HistoryTruncationStrategy`:
order-preserving + tool-call/tool-result pair atomicity.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from agentforge_core.contracts.chat import HistoryTruncationStrategy
from agentforge_core.values.chat import ChatTurn

from agentforge_chat.tokenisers import Tokeniser

SummariserCallback = Callable[[list[ChatTurn]], Awaitable[str]]
"""Async callback that turns a batch of turns into a single
summary string. The default implementation in `SummariseOldest`
concatenates contents — production users supply an LLM-backed
summariser."""

_CHARS_PER_TOKEN = 4
"""Approximate chars-per-token heuristic for `TokenBudget`."""


def _approx_tokens(turn: ChatTurn) -> int:
    return max(1, len(turn.content) // _CHARS_PER_TOKEN)


def _keep_pair_atomic(turns: list[ChatTurn]) -> list[ChatTurn]:
    """Drop a leading orphan tool turn that lost its act partner.

    The truncation contract says tool-call/tool-result pairs must
    not be split. We enforce by dropping any tool turn whose
    preceding assistant turn isn't in the selection.
    """
    if not turns:
        return turns
    out: list[ChatTurn] = []
    last_role: str | None = None
    for t in turns:
        if t.role == "tool" and last_role != "assistant":
            continue
        out.append(t)
        last_role = t.role
    return out


class SlidingWindow(HistoryTruncationStrategy):
    """Keep the most recent ``max_turns`` turns."""

    def __init__(self, max_turns: int = 50) -> None:
        if max_turns < 1:
            raise ValueError(f"max_turns must be >= 1, got {max_turns}")
        self.max_turns = max_turns

    async def select(
        self,
        all_turns: list[ChatTurn],
        next_user_message: str,
        context: Mapping[str, Any],
    ) -> list[ChatTurn]:
        del next_user_message, context
        kept = all_turns[-self.max_turns :]
        return _keep_pair_atomic(kept)


class TokenBudget(HistoryTruncationStrategy):
    """Keep recent turns until ``max_tokens`` is exhausted.

    Token counting defaults to the 4-chars-per-token heuristic.
    Pass a ``tokeniser`` callable to use a provider-aware
    encoder — e.g. :func:`agentforge_chat.tokenisers.tiktoken_tokeniser`
    for OpenAI-compatible models or
    :func:`agentforge_chat.tokenisers.anthropic_tokeniser` for
    Anthropic. The callable maps a string to its token count.
    """

    def __init__(
        self,
        max_tokens: int = 64_000,
        *,
        tokeniser: Tokeniser | None = None,
    ) -> None:
        if max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {max_tokens}")
        self.max_tokens = max_tokens
        self._tokeniser = tokeniser

    def _tokens_for_text(self, text: str) -> int:
        if self._tokeniser is None:
            return max(1, len(text) // _CHARS_PER_TOKEN)
        return max(0, int(self._tokeniser(text)))

    def _tokens_for_turn(self, turn: ChatTurn) -> int:
        if self._tokeniser is None:
            return _approx_tokens(turn)
        return max(1, int(self._tokeniser(turn.content)))

    async def select(
        self,
        all_turns: list[ChatTurn],
        next_user_message: str,
        context: Mapping[str, Any],
    ) -> list[ChatTurn]:
        del context
        # Reserve budget for the next user message itself.
        reserved = self._tokens_for_text(next_user_message)
        remaining = self.max_tokens - reserved
        chosen: list[ChatTurn] = []
        for turn in reversed(all_turns):
            cost = self._tokens_for_turn(turn)
            if cost > remaining:
                break
            chosen.append(turn)
            remaining -= cost
        chosen.reverse()
        return _keep_pair_atomic(chosen)


class SummariseOldest(HistoryTruncationStrategy):
    """Keep the last ``threshold_turns``; condense older turns
    into a single ``system`` summary turn."""

    def __init__(
        self,
        *,
        threshold_turns: int = 30,
        summariser: SummariserCallback | None = None,
    ) -> None:
        if threshold_turns < 1:
            raise ValueError(f"threshold_turns must be >= 1, got {threshold_turns}")
        self.threshold_turns = threshold_turns
        self.summariser: SummariserCallback = (
            summariser if summariser is not None else _default_summariser
        )

    async def select(
        self,
        all_turns: list[ChatTurn],
        next_user_message: str,
        context: Mapping[str, Any],
    ) -> list[ChatTurn]:
        del next_user_message, context
        if len(all_turns) <= self.threshold_turns:
            return _keep_pair_atomic(list(all_turns))
        older = all_turns[: -self.threshold_turns]
        recent = all_turns[-self.threshold_turns :]
        summary_text = await self.summariser(older)
        summary = ChatTurn(
            id=f"summary-{older[0].id}-{older[-1].id}",
            session_id=older[0].session_id,
            role="system",
            content=f"[Summary of {len(older)} older turns] {summary_text}",
            timestamp=older[0].timestamp,
            metadata={"agentforge_chat.summary": True},
        )
        return _keep_pair_atomic([summary, *recent])


class Hybrid(HistoryTruncationStrategy):
    """Compose strategies in series: each runs against the
    previous strategy's output."""

    def __init__(self, *strategies: HistoryTruncationStrategy) -> None:
        if not strategies:
            raise ValueError("Hybrid requires at least one strategy")
        self.strategies = strategies

    async def select(
        self,
        all_turns: list[ChatTurn],
        next_user_message: str,
        context: Mapping[str, Any],
    ) -> list[ChatTurn]:
        current = list(all_turns)
        for s in self.strategies:
            current = await s.select(current, next_user_message, context)
        return current


async def _default_summariser(turns: list[ChatTurn]) -> str:
    pieces = [f"{t.role}: {t.content}" for t in turns]
    return " | ".join(pieces)[:2000]


__all__ = [
    "Hybrid",
    "SlidingWindow",
    "SummariseOldest",
    "TokenBudget",
]
