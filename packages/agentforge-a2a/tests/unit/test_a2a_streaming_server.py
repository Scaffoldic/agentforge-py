"""Unit tests for `POST /a2a/v1/calls/stream` (feat-014 v0.2)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from agentforge import EnvBearerAuth
from agentforge.agent import Agent
from agentforge.runtime import RUNTIME_KEY
from agentforge_a2a import A2AServer
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


class _ThreeStepStrategy(ReasoningStrategy):
    """Appends three deterministic steps then finishes."""

    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.0)
        state.steps.append(Step(iteration=0, kind="think", content="thinking"))
        state.steps.append(Step(iteration=1, kind="act", content="calling_tool", tool_call=None))
        state.steps.append(Step(iteration=2, kind="observe", content="tool_obs"))
        return state


class _BoomStrategy(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        msg = "strategy exploded"
        raise RuntimeError(msg)


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


def _agent(strategy: ReasoningStrategy) -> Agent:
    return Agent(model=_FakeLLM(), strategy=strategy)


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> A2AServer:
    monkeypatch.setenv("A2A_TOKENS", "good")
    return A2AServer(
        agent=_agent(_ThreeStepStrategy()),
        auth=EnvBearerAuth("A2A_TOKENS"),
        endpoints=["verify"],
    )


@pytest.fixture
def client(server: A2AServer) -> TestClient:
    return TestClient(server.app)


def _auth(token: str = "good") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _parse_sse(body: bytes) -> list[dict[str, Any]]:
    return [
        json.loads(line[len("data: ") :])
        for line in body.decode("utf-8").splitlines()
        if line.startswith("data: ")
    ]


def test_stream_emits_step_chunks_then_done(client: TestClient) -> None:
    r = client.post(
        "/a2a/v1/calls/stream",
        json={"endpoint": "verify", "payload": {}},
        headers=_auth(),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    chunks = _parse_sse(r.content)
    kinds = [c["kind"] for c in chunks]
    # 3 steps mapped to step/tool_call/tool_result, then done.
    assert kinds == ["step", "tool_call", "tool_result", "done"]
    done = chunks[-1]
    assert done["run_id"] is not None
    assert "output" in done["content"]


def test_stream_missing_bearer_returns_401(client: TestClient) -> None:
    r = client.post("/a2a/v1/calls/stream", json={"endpoint": "verify", "payload": {}})
    assert r.status_code == 401


def test_stream_unknown_endpoint_emits_error_chunk(client: TestClient) -> None:
    r = client.post(
        "/a2a/v1/calls/stream",
        json={"endpoint": "nope", "payload": {}},
        headers=_auth(),
    )
    assert r.status_code == 200
    chunks = _parse_sse(r.content)
    assert len(chunks) == 1
    assert chunks[0]["kind"] == "error"
    assert chunks[0]["content"]["error"] == "unknown_endpoint"


def test_stream_propagates_parent_run_id(client: TestClient) -> None:
    r = client.post(
        "/a2a/v1/calls/stream",
        json={"endpoint": "verify", "payload": {}},
        headers={**_auth(), "X-AgentForge-Run-Id": "abc-123"},
    )
    chunks = _parse_sse(r.content)
    assert all(c["parent_run_id"] == "abc-123" for c in chunks)


def test_stream_strategy_error_surfaces_as_error_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("A2A_TOKENS", "good")
    boom_server = A2AServer(
        agent=_agent(_BoomStrategy()),
        auth=EnvBearerAuth("A2A_TOKENS"),
        endpoints=["verify"],
    )
    boom_client = TestClient(boom_server.app)
    r = boom_client.post(
        "/a2a/v1/calls/stream",
        json={"endpoint": "verify", "payload": {}},
        headers=_auth(),
    )
    chunks = _parse_sse(r.content)
    assert chunks[-1]["kind"] == "error"
    assert chunks[-1]["content"]["error"] in {"RuntimeError", "AgentRunError"}


def test_stream_budget_header_caps_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("A2A_TOKENS", "good")
    agent = _agent(_ThreeStepStrategy())
    server = A2AServer(
        agent=agent,
        auth=EnvBearerAuth("A2A_TOKENS"),
        endpoints=["verify"],
    )
    original_budget_usd = agent._budget.usd
    client = TestClient(server.app)
    r = client.post(
        "/a2a/v1/calls/stream",
        json={"endpoint": "verify", "payload": {}},
        headers={**_auth(), "X-AgentForge-Budget-Usd": "0.001"},
    )
    assert r.status_code == 200
    # Budget is restored after the call returns.
    assert agent._budget.usd == original_budget_usd
    # Hook list is empty again — no leak across calls.
    assert agent._on_step == []
