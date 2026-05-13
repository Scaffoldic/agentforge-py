"""Unit tests for `SlackChatAdapter`."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from agentforge.agent import Agent
from agentforge_chat import ChatSession
from agentforge_chat.history import InMemoryChatHistory
from agentforge_chat_slack import SlackChatAdapter
from agentforge_chat_slack._inmem_runner import FakeSlackRunner
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.chat import StreamingEvent
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolSpec,
)
from agentforge_core.values.state import AgentState


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


class _StreamingStrategy(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[StreamingEvent]:
        cumulative = ""
        for piece in ("Hel", "lo, ", "world"):
            cumulative += piece
            yield StreamingEvent(kind="text", content=piece, cumulative_text=cumulative)
        yield StreamingEvent(kind="done", content={"run_id": state.run_id, "cost_usd": 0.0})


def _agent() -> Agent:
    return Agent(model=_FakeLLM(), strategy=_StreamingStrategy())


@pytest.mark.asyncio
async def test_handle_event_posts_placeholder_then_final_text() -> None:
    runner = FakeSlackRunner()
    adapter = SlackChatAdapter(
        session_factory=lambda channel_id: ChatSession(
            agent=_agent(),
            session_id=channel_id,
            history_store=InMemoryChatHistory(),
        ),
        runner=runner,
        batch_window_s=0.0,  # flush every chunk
    )
    await adapter.handle_event("C-final-text", "hi")
    # One placeholder post; at least one update; final update has the
    # cumulative agent text.
    assert len(runner.posted) == 1
    assert runner.posted[0].channel == "C-final-text"
    assert len(runner.updates) >= 1
    assert runner.updates[-1].text == "Hello, world"


@pytest.mark.asyncio
async def test_handle_event_reuses_session_per_channel() -> None:
    runner = FakeSlackRunner()
    builds = 0

    def factory(channel_id: str) -> ChatSession:
        nonlocal builds
        builds += 1
        return ChatSession(
            agent=_agent(),
            session_id=channel_id,
            history_store=InMemoryChatHistory(),
        )

    adapter = SlackChatAdapter(
        session_factory=factory,
        runner=runner,
        batch_window_s=0.0,
    )
    await adapter.handle_event("C-reuse", "first")
    await adapter.handle_event("C-reuse", "second")
    # Same channel ID → factory only called once.
    assert builds == 1
