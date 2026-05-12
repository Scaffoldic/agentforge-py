"""Unit tests for `A2ABridge` (feat-014 chunk 4)."""

from __future__ import annotations

import asyncio

import pytest
from agentforge import EnvBearerAuth
from agentforge.agent import Agent
from agentforge.runtime import RUNTIME_KEY
from agentforge_a2a import A2ABridge
from agentforge_a2a._inmem_runner import FakeA2AClientRunner, FakeA2AServerRunner
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolSpec,
)
from agentforge_core.values.state import AgentState, Step
from pydantic import ValidationError


class _S(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.0)
        state.steps.append(Step(iteration=0, kind="think", content="ok"))
        return state


class _L(LLMClient):
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
    return Agent(model=_L(), strategy=_S())


def test_bridge_client_only_mode() -> None:
    config = {
        "peers": [
            {
                "name": "fact-checker",
                "url": "https://example/a2a",
                "auth": {"type": "bearer", "token": "t"},
            },
        ],
    }
    bridge = A2ABridge.from_config(
        config,
        client_runner=FakeA2AClientRunner(),
    )
    assert "fact-checker" in bridge.peers
    assert bridge.server is None


def test_bridge_validates_extra_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        A2ABridge.from_config(
            {"peers": [], "unknown_field": 1},
            client_runner=FakeA2AClientRunner(),
        )


def test_bridge_with_expose_requires_agent_and_auth() -> None:
    config = {
        "peers": [],
        "expose": {
            "enabled": True,
            "host": "0.0.0.0",
            "port": 8080,
            "endpoints": [{"name": "verify"}],
        },
    }
    with pytest.raises(ValueError, match="requires both an Agent and an AuthPolicy"):
        A2ABridge.from_config(
            config,
            client_runner=FakeA2AClientRunner(),
        )


def test_bridge_with_expose_builds_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_TOKENS", "good")
    config = {
        "peers": [],
        "expose": {
            "enabled": True,
            "endpoints": [{"name": "verify"}],
        },
    }
    server_runner = FakeA2AServerRunner()
    bridge = A2ABridge.from_config(
        config,
        agent=_agent(),
        auth=EnvBearerAuth("A2A_TOKENS"),
        client_runner=FakeA2AClientRunner(),
        server_runner=server_runner,
    )
    assert bridge.server is not None
    assert bridge.server.endpoints == ("verify",)


@pytest.mark.asyncio
async def test_bridge_start_then_close(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_TOKENS", "good")
    config = {
        "peers": [],
        "expose": {
            "enabled": True,
            "endpoints": [{"name": "verify"}],
        },
    }
    server_runner = FakeA2AServerRunner()
    bridge = A2ABridge.from_config(
        config,
        agent=_agent(),
        auth=EnvBearerAuth("A2A_TOKENS"),
        client_runner=FakeA2AClientRunner(),
        server_runner=server_runner,
    )
    await bridge.start()
    # Yield once so the background task runs serve().
    await asyncio.sleep(0)
    assert server_runner.serving is True
    await bridge.close()
    assert server_runner.stop_called is True


@pytest.mark.asyncio
async def test_bridge_close_closes_client_runners() -> None:
    runner = FakeA2AClientRunner()
    bridge = A2ABridge.from_config(
        {
            "peers": [
                {
                    "name": "x",
                    "url": "https://x/a2a",
                    "auth": {"type": "bearer", "token": "t"},
                }
            ],
        },
        client_runner=runner,
    )
    await bridge.close()
    assert runner.closed is True
