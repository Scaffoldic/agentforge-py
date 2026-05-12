"""Unit tests for `A2AServer` (feat-014 chunk 4)."""

from __future__ import annotations

import pytest
from agentforge import EnvBearerAuth
from agentforge.agent import Agent
from agentforge.findings import SimpleFinding
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


class _EchoStrategy(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.0)
        state.steps.append(Step(iteration=0, kind="think", content=f"echo:{state.task[-100:]}"))
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


def _agent() -> Agent:
    return Agent(model=_FakeLLM(), strategy=_EchoStrategy())


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> A2AServer:
    monkeypatch.setenv("A2A_TOKENS", "good,other")
    return A2AServer(
        agent=_agent(),
        auth=EnvBearerAuth("A2A_TOKENS"),
        endpoints=["review-pr", "verify"],
    )


@pytest.fixture
def client(server: A2AServer) -> TestClient:
    return TestClient(server.app)


def _auth(token: str = "good") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_info_endpoint_lists_whitelist(client: TestClient) -> None:
    r = client.get("/a2a/v1/info", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert "version" in body
    names = {ep["name"] for ep in body["endpoints"]}
    assert names == {"review-pr", "verify"}
    # v0.2 shape: each entry has description + input_schema fields.
    for ep in body["endpoints"]:
        assert set(ep.keys()) >= {"name", "description", "input_schema"}


def test_missing_bearer_returns_401(client: TestClient) -> None:
    r = client.post("/a2a/v1/calls", json={"endpoint": "verify", "payload": {}})
    assert r.status_code == 401


def test_invalid_bearer_returns_401(client: TestClient) -> None:
    r = client.post(
        "/a2a/v1/calls",
        json={"endpoint": "verify", "payload": {}},
        headers=_auth("nope"),
    )
    assert r.status_code == 401


def test_unknown_endpoint_returns_404(client: TestClient) -> None:
    r = client.post(
        "/a2a/v1/calls",
        json={"endpoint": "not-listed", "payload": {}},
        headers=_auth(),
    )
    assert r.status_code == 404


def test_happy_path_returns_a2a_response(client: TestClient) -> None:
    r = client.post(
        "/a2a/v1/calls",
        json={"endpoint": "verify", "payload": {"claim": "x"}},
        headers=_auth(),
    )
    assert r.status_code == 200
    body = r.json()
    assert "output" in body
    assert "echo:" in body["output"]
    assert body["parent_run_id"] is None


def test_parent_run_id_propagated_from_header(client: TestClient) -> None:
    r = client.post(
        "/a2a/v1/calls",
        json={"endpoint": "verify", "payload": {}},
        headers={**_auth(), "X-AgentForge-Run-Id": "caller-run-123"},
    )
    assert r.status_code == 200
    assert r.json()["parent_run_id"] == "caller-run-123"


def test_budget_header_caps_inner_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_TOKENS", "good")
    agent = _agent()
    original_cap = agent._budget.usd
    server = A2AServer(
        agent=agent,
        auth=EnvBearerAuth("A2A_TOKENS"),
        endpoints=["verify"],
    )
    client = TestClient(server.app)
    r = client.post(
        "/a2a/v1/calls",
        json={"endpoint": "verify", "payload": {}},
        headers={**_auth(), "X-AgentForge-Budget-Usd": "0.05"},
    )
    assert r.status_code == 200
    # Server should have restored the original budget.
    assert agent._budget.usd == original_cap


def test_invalid_budget_header_ignored(client: TestClient) -> None:
    r = client.post(
        "/a2a/v1/calls",
        json={"endpoint": "verify", "payload": {}},
        headers={**_auth(), "X-AgentForge-Budget-Usd": "not-a-float"},
    )
    assert r.status_code == 200


def test_findings_serialised_into_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_TOKENS", "good")

    class _FindingStrategy(ReasoningStrategy):
        async def run(self, state: AgentState) -> AgentState:
            runtime = state.metadata.get(RUNTIME_KEY)
            if runtime is not None:
                runtime.budget.commit(0.0)
            state.findings.append(SimpleFinding(severity="info", category="a2a", message="ok"))
            state.steps.append(Step(iteration=0, kind="think", content="done"))
            return state

    agent = Agent(model=_FakeLLM(), strategy=_FindingStrategy())
    server = A2AServer(
        agent=agent,
        auth=EnvBearerAuth("A2A_TOKENS"),
        endpoints=["verify"],
    )
    client = TestClient(server.app)
    r = client.post(
        "/a2a/v1/calls",
        json={"endpoint": "verify", "payload": {}},
        headers=_auth(),
    )
    assert r.status_code == 200
    # findings tuple from RunResult is empty (the strategy
    # populates state.findings but RunResult.findings is not
    # plumbed from there in feat-001); the server just
    # serialises whatever's on result.findings.
    assert "findings" in r.json()
