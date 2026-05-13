"""`ChatSession.stream()` per-token path (feat-020 v0.2 follow-up)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from agentforge.agent import Agent
from agentforge_chat import ChatSession
from agentforge_chat.history import InMemoryChatHistory
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.chat import StreamingEvent
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolSpec,
)
from agentforge_core.values.state import AgentState, Step


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
            model="x",
            provider="x",
        )

    async def close(self) -> None:
        return None


class _PerTokenStrategy(ReasoningStrategy):
    """Emits three text events + a done; overrides ABC stream()."""

    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="think", content="Hello, world"))
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[StreamingEvent]:
        cumulative = ""
        for piece in ("Hel", "lo, ", "world"):
            cumulative += piece
            yield StreamingEvent(kind="text", content=piece, cumulative_text=cumulative)
        state.steps.append(Step(iteration=0, kind="think", content=cumulative))
        yield StreamingEvent(
            kind="done",
            content={"run_id": state.run_id, "cost_usd": 0.0},
        )


@pytest.mark.asyncio
async def test_chat_session_forwards_per_token_events() -> None:
    agent = Agent(model=_FakeLLM(), strategy=_PerTokenStrategy())
    session = ChatSession(
        agent=agent,
        session_id="s1",
        history_store=InMemoryChatHistory(),
    )
    chunks = [chunk async for chunk in await session.stream("Hi")]
    kinds = [c.kind for c in chunks]
    # 3 text chunks from the strategy + 1 done emitted by ChatSession
    # after persistence + budget accounting.
    assert kinds == ["text", "text", "text", "done"]
    assert chunks[-1].content is not None
    # Assistant turn was persisted with the cumulative text.
    history = await session.history()
    assert [t.role for t in history] == ["user", "assistant"]
    assert history[-1].content == "Hello, world"


class _DefaultStreamStrategy(ReasoningStrategy):
    """No override — uses the ABC default stream()."""

    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="think", content="buffered"))
        return state


@pytest.mark.asyncio
async def test_chat_session_falls_back_to_buffered_stream_without_override() -> None:
    agent = Agent(model=_FakeLLM(), strategy=_DefaultStreamStrategy())
    session = ChatSession(
        agent=agent,
        session_id="s2",
        history_store=InMemoryChatHistory(),
    )
    chunks = [chunk async for chunk in await session.stream("Hi")]
    # Buffer-then-stream path emits at least one text chunk + done.
    kinds = [c.kind for c in chunks]
    assert kinds[-1] == "done"
    assert "text" in kinds
