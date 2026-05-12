"""Unit tests for A2A discovery (feat-014 v0.2 follow-up)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from agentforge import EnvBearerAuth
from agentforge.agent import Agent
from agentforge.runtime import RUNTIME_KEY
from agentforge_a2a import (
    A2ABridge,
    A2APeer,
    A2APeerInfo,
    A2AServer,
    BearerAuth,
    discover_peer,
)
from agentforge_a2a._inmem_runner import FakeA2AClientRunner
from agentforge_a2a.values import A2AEndpointConfig
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolSpec,
)
from agentforge_core.values.state import AgentState, Step
from fastapi.testclient import TestClient


class _Strategy(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.0)
        state.steps.append(Step(iteration=0, kind="think", content="ok"))
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
            model="x",
            provider="x",
        )

    async def close(self) -> None:
        return None


def _peer(runner: FakeA2AClientRunner) -> A2APeer:
    return A2APeer(
        name="alpha",
        url="https://peer.example.com/a2a/v1/calls",
        auth=BearerAuth("tok"),
        runner=runner,
    )


def test_discover_peer_parses_info_payload() -> None:
    runner = FakeA2AClientRunner(
        get_response={
            "version": "0.1",
            "server_name": "alpha",
            "endpoints": [
                {"name": "review-pr", "description": "Review", "input_schema": {}},
                {"name": "verify", "description": "Verify", "input_schema": {"k": 1}},
            ],
            "metadata": {},
        }
    )
    info = asyncio.run(discover_peer(_peer(runner)))
    assert isinstance(info, A2APeerInfo)
    assert info.version == "0.1"
    assert info.server_name == "alpha"
    assert [e.name for e in info.endpoints] == ["review-pr", "verify"]
    # info URL is derived: /calls -> /info
    assert runner.get_calls[0].url == "https://peer.example.com/a2a/v1/info"
    # Bearer header propagated
    assert runner.get_calls[0].headers["Authorization"] == "Bearer tok"


def test_discover_peer_handles_url_without_calls_suffix() -> None:
    runner = FakeA2AClientRunner(get_response={"version": "0.1"})
    peer = A2APeer(
        name="beta",
        url="https://peer.example.com/api",
        auth=BearerAuth("tok"),
        runner=runner,
    )
    asyncio.run(discover_peer(peer))
    assert runner.get_calls[0].url == "https://peer.example.com/api/info"


def test_bridge_discover_all_populates_peer_info() -> None:
    runner_a = FakeA2AClientRunner(
        get_response={"version": "0.1", "server_name": "a", "endpoints": []}
    )
    runner_b = FakeA2AClientRunner(
        get_response={"version": "0.1", "server_name": "b", "endpoints": []}
    )
    peers = {
        "a": A2APeer(
            name="a",
            url="https://a.example.com/a2a/v1/calls",
            auth=BearerAuth("t"),
            runner=runner_a,
        ),
        "b": A2APeer(
            name="b",
            url="https://b.example.com/a2a/v1/calls",
            auth=BearerAuth("t"),
            runner=runner_b,
        ),
    }
    bridge = A2ABridge(peers=peers)
    info_map = asyncio.run(bridge.discover_all())
    assert set(info_map) == {"a", "b"}
    assert info_map["a"].server_name == "a"
    assert info_map["b"].server_name == "b"
    # peer_info exposes the cache (defensive copy).
    cached = bridge.peer_info
    assert set(cached) == {"a", "b"}
    cached.clear()
    assert set(bridge.peer_info) == {"a", "b"}


def test_info_endpoint_returns_rich_descriptors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("A2A_TOKENS", "good")
    agent = Agent(model=_FakeLLM(), strategy=_Strategy())
    server = A2AServer(
        agent=agent,
        auth=EnvBearerAuth("A2A_TOKENS"),
        endpoints=["review-pr", "verify"],
        endpoint_descriptors=[
            A2AEndpointConfig(
                name="review-pr",
                description="Review a PR diff",
                accepts={"type": "object", "properties": {"diff": {"type": "string"}}},
            ),
            A2AEndpointConfig(name="verify", description="Run verifier", accepts={}),
        ],
        server_name="alpha-prod",
    )
    client = TestClient(server.app)
    r = client.get("/a2a/v1/info", headers={"Authorization": "Bearer good"})
    assert r.status_code == 200
    body: dict[str, Any] = r.json()
    assert body["server_name"] == "alpha-prod"
    by_name = {ep["name"]: ep for ep in body["endpoints"]}
    assert by_name["review-pr"]["description"] == "Review a PR diff"
    assert by_name["review-pr"]["input_schema"] == {
        "type": "object",
        "properties": {"diff": {"type": "string"}},
    }
    # An endpoint name with no descriptor still shows up, with empties.
    assert by_name["verify"]["input_schema"] == {}
