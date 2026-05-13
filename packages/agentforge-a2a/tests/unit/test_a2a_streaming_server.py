"""Unit tests for `POST /a2a/v1/calls/stream` (feat-014 v0.3).

v0.3 swaps the server from a one-off `_on_step` hook to driving
``Agent.stream(task)`` and forwarding each ``StreamingEvent`` as
an ``A2AChunk`` frame. Strategies that override
``ReasoningStrategy.stream`` emit per-token text; strategies that
don't fall through to the default base-class ``stream`` and emit
a single ``done``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from agentforge import EnvBearerAuth
from agentforge.agent import Agent
from agentforge.runtime import RUNTIME_KEY
from agentforge_a2a import A2AServer
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
from fastapi.testclient import TestClient


class _PerTokenStrategy(ReasoningStrategy):
    """Overrides `stream()` to emit three text tokens then done.

    Demonstrates the v0.3 per-token contract: the strategy itself
    decides chunk granularity; the A2A server forwards events as
    SSE frames without inspecting agent steps.
    """

    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.0)
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[StreamingEvent]:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.0)
        for tok in ("Hello, ", "world", "!"):
            yield StreamingEvent(kind="text", content=tok)
        # Agent._extract_output reads the last non-system step's
        # content; append one so the canonical `done` chunk carries
        # the assembled text.
        state.steps.append(Step(iteration=0, kind="synthesize", content="Hello, world!"))
        yield StreamingEvent(
            kind="done",
            content={"run_id": state.run_id, "cost_usd": 0.0, "output": "Hello, world!"},
        )


class _SilentStrategy(ReasoningStrategy):
    """Doesn't override `stream`; falls through to the default
    base-class implementation that yields one terminal `done`."""

    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.0)
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
        agent=_agent(_PerTokenStrategy()),
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


def test_stream_emits_per_token_text_then_done(client: TestClient) -> None:
    r = client.post(
        "/a2a/v1/calls/stream",
        json={"endpoint": "verify", "payload": {}},
        headers=_auth(),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    chunks = _parse_sse(r.content)
    kinds = [c["kind"] for c in chunks]
    assert kinds == ["text", "text", "text", "done"]
    text_chunks = [c["content"] for c in chunks if c["kind"] == "text"]
    assert text_chunks == ["Hello, ", "world", "!"]
    done = chunks[-1]
    assert done["run_id"]
    assert done["content"]["output"] == "Hello, world!"
    assert done["content"]["cost_usd"] == 0.0


def test_stream_default_strategy_emits_only_done(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strategies that don't override `stream()` fall through to the
    default base-class implementation, which yields one terminal
    `done`. The A2A server swallows the strategy's done and emits
    its own canonical one."""
    monkeypatch.setenv("A2A_TOKENS", "good")
    silent = A2AServer(
        agent=_agent(_SilentStrategy()),
        auth=EnvBearerAuth("A2A_TOKENS"),
        endpoints=["verify"],
    )
    r = TestClient(silent.app).post(
        "/a2a/v1/calls/stream",
        json={"endpoint": "verify", "payload": {}},
        headers=_auth(),
    )
    chunks = _parse_sse(r.content)
    assert [c["kind"] for c in chunks] == ["done"]


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


def test_stream_budget_header_caps_and_restores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Budget cap is honoured for the streamed call and the original
    budget is restored when the stream finishes. v0.3 also asserts
    the server does NOT mutate `agent._on_step` (the v0.2 hook
    dance is gone)."""
    monkeypatch.setenv("A2A_TOKENS", "good")
    agent = _agent(_PerTokenStrategy())
    server = A2AServer(
        agent=agent,
        auth=EnvBearerAuth("A2A_TOKENS"),
        endpoints=["verify"],
    )
    original_budget_usd = agent._budget.usd
    hooks_before = list(agent._on_step)
    client = TestClient(server.app)
    r = client.post(
        "/a2a/v1/calls/stream",
        json={"endpoint": "verify", "payload": {}},
        headers={**_auth(), "X-AgentForge-Budget-Usd": "0.001"},
    )
    assert r.status_code == 200
    assert agent._budget.usd == original_budget_usd
    assert agent._on_step == hooks_before
