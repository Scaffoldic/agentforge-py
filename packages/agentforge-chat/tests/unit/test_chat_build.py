"""Tests for `build_chat_session_from_config` (feat-020 chunk 5)."""

from __future__ import annotations

import pytest
from agentforge.agent import Agent
from agentforge.resolver_register import register_chat_history, register_chat_truncation
from agentforge.runtime import RUNTIME_KEY
from agentforge_chat import ChatSession, build_chat_session_from_config
from agentforge_chat.history import InMemoryChatHistory
from agentforge_chat.truncation import SlidingWindow
from agentforge_core.config.schema import (
    AgentForgeConfig,
    ChatConfig,
    ChatHistoryDriverConfig,
    ChatSessionConfig,
    ChatTruncationConfig,
    ModulesConfig,
)
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolSpec,
)
from agentforge_core.values.state import AgentState, Step


class _Strat(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.0)
        state.steps.append(Step(iteration=0, kind="think", content="ok"))
        return state


class _LLM(LLMClient):
    async def call(
        self, system: str, messages: list[Message], tools: list[ToolSpec] | None = None
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


def _agent() -> Agent:
    return Agent(model=_LLM(), strategy=_Strat())


@register_chat_history("_test_inmem_chat_history")
class _Dummy(InMemoryChatHistory):
    pass


@register_chat_truncation("_test_sliding")
class _Slid(SlidingWindow):
    def __init__(self, *, max_turns: int = 20) -> None:
        super().__init__(max_turns=max_turns)


@pytest.mark.asyncio
async def test_build_chat_defaults_when_no_chat_block() -> None:
    cfg = AgentForgeConfig()
    session = await build_chat_session_from_config(cfg, _agent())
    assert isinstance(session, ChatSession)
    # Default history is InMemoryChatHistory; default truncation
    # behaves like SlidingWindow(50).
    await session.send("hi")
    assert session.turn_count == 1


@pytest.mark.asyncio
async def test_build_chat_resolves_named_driver_and_strategy() -> None:
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            chat=ChatConfig(
                history=ChatHistoryDriverConfig(driver="_test_inmem_chat_history", config={}),
                truncation=ChatTruncationConfig(strategy="_test_sliding", config={"max_turns": 3}),
                session=ChatSessionConfig(per_turn_budget_usd=1.0),
            )
        )
    )
    session = await build_chat_session_from_config(cfg, _agent())
    await session.send("hi")
    assert session.turn_count == 1
