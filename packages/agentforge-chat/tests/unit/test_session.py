"""Unit tests for `ChatSession` (feat-020 chunk 3)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
from agentforge.agent import Agent
from agentforge.runtime import RUNTIME_KEY
from agentforge_chat import ChatSession, InMemoryChatHistory, SlidingWindow
from agentforge_core.contracts.chat import HistoryTruncationStrategy
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.production.exceptions import BudgetExceeded
from agentforge_core.values.chat import ChatTurn
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
    ToolSpec,
)
from agentforge_core.values.state import AgentState, Step


class _EchoStrategy(ReasoningStrategy):
    """Strategy that appends a single 'think' step echoing the task
    and commits a fixed cost to the runtime budget."""

    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.01)
        state.steps.append(
            Step(
                iteration=0,
                kind="think",
                content=f"echo: {state.task[-200:]}",
                cost_usd=0.01,
            )
        )
        return state


class _FakeLLM(LLMClient):
    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        del system, messages, tools
        return LLMResponse(
            content="",
            tool_calls=(),
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=0, output_tokens=0),
            cost_usd=0.0,
            model="fake",
            provider="fake",
        )

    async def close(self) -> None:
        return None


def _agent() -> Agent:
    return Agent(model=_FakeLLM(), strategy=_EchoStrategy())


def _session(**kwargs: Any) -> ChatSession:
    return ChatSession(_agent(), history_store=InMemoryChatHistory(), **kwargs)


@pytest.mark.asyncio
async def test_single_turn_round_trip() -> None:
    session = _session(session_id="t1")
    response = await session.send("hi")
    assert "echo:" in response.content
    assert response.run_id


@pytest.mark.asyncio
async def test_history_remembers_prior_turn() -> None:
    session = _session(session_id="t2")
    await session.send("first message")
    await session.send("second message")
    turns = await session.history()
    # 2 user turns + 2 assistant turns
    user_contents = [t.content for t in turns if t.role == "user"]
    assert "first message" in user_contents
    assert "second message" in user_contents


@pytest.mark.asyncio
async def test_truncation_applies_to_serialised_task() -> None:
    captured: dict[str, str] = {}

    class _CapturingStrategy(ReasoningStrategy):
        async def run(self, state: AgentState) -> AgentState:
            captured["task"] = state.task
            state.steps.append(Step(iteration=0, kind="think", content="ok"))
            return state

    agent = Agent(model=_FakeLLM(), strategy=_CapturingStrategy())
    session = ChatSession(
        agent,
        session_id="t3",
        history_store=InMemoryChatHistory(),
        truncation=SlidingWindow(max_turns=1),
        system_prompt="you are helpful.",
    )
    await session.send("first")
    await session.send("second")
    # With max_turns=1, the prior history shown to the agent is the
    # single most recent (assistant) turn before the new user line.
    assert "user: second" in captured["task"]
    assert "you are helpful." in captured["task"]


@pytest.mark.asyncio
async def test_idempotency_returns_cached_response() -> None:
    session = _session(session_id="t4")
    r1 = await session.send("hi", idempotency_key="abc")
    r2 = await session.send("ignored second body", idempotency_key="abc")
    assert r1.turn_id == r2.turn_id
    assert r1.content == r2.content
    # second send must NOT have appended new turns
    turns = await session.history()
    user_count = sum(1 for t in turns if t.role == "user")
    assert user_count == 1


@pytest.mark.asyncio
async def test_per_turn_budget_enforced() -> None:
    session = _session(session_id="t5", per_turn_budget_usd=0.001)
    with pytest.raises(BudgetExceeded, match="per-turn"):
        await session.send("hi")


@pytest.mark.asyncio
async def test_per_session_budget_enforced() -> None:
    session = _session(session_id="t6", per_session_budget_usd=0.015)
    await session.send("first")  # commits 0.01 cost
    with pytest.raises(BudgetExceeded, match="per-session"):
        await session.send("second")  # 0.01 + 0.01 > 0.015


@pytest.mark.asyncio
async def test_per_session_lock_serialises_concurrent_sends() -> None:
    session = _session(session_id="t7")
    results = await asyncio.gather(
        session.send("a"),
        session.send("b"),
    )
    assert len(results) == 2
    turns = await session.history()
    # Lock serialises: histories of user turns reflect both messages in
    # some order.
    user_contents = {t.content for t in turns if t.role == "user"}
    assert user_contents == {"a", "b"}


@pytest.mark.asyncio
async def test_reset_clears_history_and_counters() -> None:
    session = _session(session_id="t8")
    await session.send("hi")
    assert session.turn_count == 1
    await session.reset()
    assert session.turn_count == 0
    assert session.total_cost_usd == 0.0
    assert await session.history() == []


@pytest.mark.asyncio
async def test_on_turn_hook_fires_for_user_and_assistant() -> None:
    seen: list[ChatTurn] = []

    def hook(turn: ChatTurn) -> None:
        seen.append(turn)

    session = _session(session_id="t9", on_turn=hook)
    await session.send("hi")
    roles = [t.role for t in seen]
    assert "user" in roles
    assert "assistant" in roles


@pytest.mark.asyncio
async def test_stream_yields_text_and_done_chunks() -> None:
    session = _session(session_id="t10")
    chunks = [chunk async for chunk in await session.stream("hi there.")]
    kinds = [c.kind for c in chunks]
    assert "text" in kinds
    assert kinds[-1] == "done"
    # cumulative_text on text chunks grows monotonically
    cumulative = [c.cumulative_text for c in chunks if c.kind == "text"]
    assert cumulative == sorted(cumulative, key=lambda s: len(s) if s else 0)


@pytest.mark.asyncio
async def test_stream_emits_error_chunk_on_budget_breach() -> None:
    session = _session(session_id="t11", per_turn_budget_usd=0.0001)
    chunks = [chunk async for chunk in await session.stream("hi")]
    assert chunks[-1].kind == "error"
    assert "BudgetExceeded" in chunks[-1].content["reason"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_cancellation_pre_llm_raises() -> None:
    session = _session(session_id="t12")
    event = asyncio.Event()
    event.set()
    with pytest.raises(asyncio.CancelledError):
        await session.send("hi", cancellation=event)


class _ConstantSelect(HistoryTruncationStrategy):
    async def select(
        self,
        all_turns: list[ChatTurn],
        next_user_message: str,
        context: Mapping[str, Any],
    ) -> list[ChatTurn]:
        del next_user_message, context
        return list(all_turns)


@pytest.mark.asyncio
async def test_custom_truncation_strategy_is_invoked() -> None:
    session = _session(session_id="t13", truncation=_ConstantSelect())
    await session.send("first")
    await session.send("second")
    turns = await session.history()
    assert len(turns) >= 4  # 2 user + 2 assistant


@pytest.mark.asyncio
async def test_close_is_idempotent() -> None:
    session = _session(session_id="t14")
    await session.close()
    await session.close()


# ----------------------------------------------------------------------
# bug-010 — persist intermediate tool steps to history
# ----------------------------------------------------------------------


class _ToolUseStrategy(ReasoningStrategy):
    """Strategy that simulates one think/act/observe iteration with a
    tool call, then a final think with the answer. Used to exercise
    bug-010 persistence."""

    def __init__(self, *, tool_id: str = "tc-1", tool_name: str = "ping") -> None:
        self._tool_id = tool_id
        self._tool_name = tool_name

    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.01)
        tc = ToolCall(id=self._tool_id, name=self._tool_name, arguments={"target": "x"})
        state.steps.append(Step(iteration=0, kind="think", content="planning"))
        state.steps.append(
            Step(
                iteration=0,
                kind="act",
                content={"tool": tc.name, "arguments": dict(tc.arguments)},
                tool_call=tc,
                cost_usd=0.0,
            )
        )
        state.steps.append(
            Step(
                iteration=0,
                kind="observe",
                content='{"ok": true}',
                tool_call=tc,
                cost_usd=0.0,
            )
        )
        state.steps.append(
            Step(iteration=1, kind="think", content="all good", cost_usd=0.01),
        )
        return state


def _tool_session(**kwargs: Any) -> ChatSession:
    agent = Agent(model=_FakeLLM(), strategy=_ToolUseStrategy())
    return ChatSession(agent, history_store=InMemoryChatHistory(), **kwargs)


@pytest.mark.asyncio
async def test_persist_steps_records_act_and_observe_turns() -> None:
    """bug-010: tool steps from result.steps must persist to chat history
    so generative-UI clients can render them and the next turn's prompt
    sees prior tool context."""
    session = _tool_session(session_id="t-bug010-run")
    await session.send("do the thing")
    turns = await session.history()
    roles_then_ids = [(t.role, t.tool_call_id, t.tool_calls) for t in turns]
    # Expected shape: user, assistant(act with tool_calls), tool(observation),
    # assistant(final answer).
    assert [r for r, _, _ in roles_then_ids] == ["user", "assistant", "tool", "assistant"]
    _, _, act_tcs = roles_then_ids[1]
    assert len(act_tcs) == 1
    assert act_tcs[0].id == "tc-1"
    assert act_tcs[0].name == "ping"
    _, observe_tcid, _ = roles_then_ids[2]
    assert observe_tcid == "tc-1"


@pytest.mark.asyncio
async def test_response_tool_calls_populated_from_steps() -> None:
    """bug-010: ChatResponse.tool_calls aggregates the tool calls from
    `result.steps` instead of being the previously-hardcoded empty tuple."""
    session = _tool_session(session_id="t-bug010-resp")
    response = await session.send("do the thing")
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].id == "tc-1"


@pytest.mark.asyncio
async def test_persist_steps_false_keeps_history_lean() -> None:
    """bug-010 opt-out: setting persist_steps=False reverts to the
    pre-fix shape (user + final assistant only). Useful when an
    external consumer reconstructs tool history from another source."""
    session = _tool_session(session_id="t-bug010-off", persist_steps=False)
    response = await session.send("do the thing")
    turns = await session.history()
    assert [t.role for t in turns] == ["user", "assistant"]
    # And the response still surfaces an empty tool_calls (opt-out is
    # consistent across persistence + response).
    assert response.tool_calls == ()


@pytest.mark.asyncio
async def test_stream_persists_step_turns() -> None:
    """bug-010 stream path: `_stream_per_token` must persist tool turns
    via `_persist_steps_from_events` so streaming and non-streaming
    paths produce the same on-disk shape."""
    session = _tool_session(session_id="t-bug010-stream")
    async for _ in await session.stream("do the thing"):
        pass
    turns = await session.history()
    assert [t.role for t in turns] == ["user", "assistant", "tool", "assistant"]
    # tool turn pairs by id with the prior assistant turn's tool_calls
    assert turns[1].tool_calls[0].id == turns[2].tool_call_id
