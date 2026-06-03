"""Unit tests for `ChatServer` (feat-020 chunk 4)."""

from __future__ import annotations

import os

import pytest
from agentforge.agent import Agent
from agentforge.runtime import RUNTIME_KEY
from agentforge_chat import InMemoryChatHistory
from agentforge_chat_http import ChatServer, EnvBearerAuth
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
            model="fake",
            provider="fake",
        )

    async def close(self) -> None:
        return None


def _agent_factory() -> Agent:
    return Agent(model=_FakeLLM(), strategy=_EchoStrategy())


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> ChatServer:
    monkeypatch.setenv("API_TOKENS", "good-token,other-token")
    return ChatServer(
        agent_factory=_agent_factory,
        history_store=InMemoryChatHistory(),
        auth=EnvBearerAuth("API_TOKENS"),
        host="127.0.0.1",
        port=8080,
    )


@pytest.fixture
def client(server: ChatServer) -> TestClient:
    return TestClient(server.app)


def _auth(token: str = "good-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_healthz_is_unauthenticated(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_session_returns_id(client: TestClient) -> None:
    r = client.post("/sessions", json={}, headers=_auth())
    assert r.status_code == 200
    assert "id" in r.json()


async def test_create_session_works_with_sqlite_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """bug-018: POST /sessions must not 500 on a fresh SQLite-backed server.
    `_create_session` records the owner before the first turn; the SQLite
    driver used to raise because the row didn't exist yet."""
    import httpx  # noqa: PLC0415
    from agentforge_chat import SqliteChatHistory  # noqa: PLC0415

    monkeypatch.setenv("API_TOKENS", "good-token")
    store = await SqliteChatHistory.from_path(":memory:")
    try:
        server = ChatServer(
            agent_factory=_agent_factory,
            history_store=store,
            auth=EnvBearerAuth("API_TOKENS"),
            host="127.0.0.1",
            port=8080,
        )
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/sessions", json={}, headers=_auth())
        assert r.status_code == 200
        sid = r.json()["id"]
        # The session is persisted and listable before any turn.
        listed = await store.list_sessions()
        assert sid in {s.id for s in listed}
    finally:
        await store.close()


def test_missing_bearer_returns_401(client: TestClient) -> None:
    r = client.post("/sessions", json={})
    assert r.status_code == 401


def test_invalid_bearer_returns_401(client: TestClient) -> None:
    r = client.post("/sessions", json={}, headers=_auth("nope"))
    assert r.status_code == 401


def test_post_message_returns_response(client: TestClient) -> None:
    sid = client.post("/sessions", json={}, headers=_auth()).json()["id"]
    r = client.post(
        f"/sessions/{sid}/messages",
        json={"content": "hi"},
        headers=_auth(),
    )
    assert r.status_code == 200
    body = r.json()
    assert "content" in body
    assert "echo:" in body["content"]


def test_cross_owner_access_returns_403(client: TestClient) -> None:
    sid = client.post("/sessions", json={}, headers=_auth("good-token")).json()["id"]
    r = client.post(
        f"/sessions/{sid}/messages",
        json={"content": "hi"},
        headers=_auth("other-token"),
    )
    assert r.status_code == 403


def test_get_history_returns_turns(client: TestClient) -> None:
    sid = client.post("/sessions", json={}, headers=_auth()).json()["id"]
    client.post(
        f"/sessions/{sid}/messages",
        json={"content": "hi"},
        headers=_auth(),
    )
    r = client.get(f"/sessions/{sid}/messages", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert any(t["role"] == "user" for t in body)
    assert any(t["role"] == "assistant" for t in body)


def test_delete_session_cascades(client: TestClient) -> None:
    sid = client.post("/sessions", json={}, headers=_auth()).json()["id"]
    client.post(
        f"/sessions/{sid}/messages",
        json={"content": "hi"},
        headers=_auth(),
    )
    r = client.delete(f"/sessions/{sid}", headers=_auth())
    assert r.status_code == 204
    after = client.get(f"/sessions/{sid}/messages", headers=_auth())
    assert after.status_code == 200
    assert after.json() == []


def test_list_sessions_filters_by_owner(client: TestClient) -> None:
    client.post("/sessions", json={}, headers=_auth("good-token"))
    client.post("/sessions", json={}, headers=_auth("other-token"))
    mine = client.get("/sessions", headers=_auth("good-token")).json()
    assert all(s["owner"] == "good-token" for s in mine)


def test_sse_streaming_returns_chunks(client: TestClient) -> None:
    sid = client.post("/sessions", json={}, headers=_auth()).json()["id"]
    headers = {**_auth(), "Accept": "text/event-stream"}
    with client.stream(
        "POST",
        f"/sessions/{sid}/messages",
        json={"content": "hi there. how are you?"},
        headers=headers,
    ) as r:
        assert r.status_code == 200
        payload = "".join(r.iter_text())
    # SSE frames start with `data: `; at least one text + one done chunk.
    assert '"kind":"text"' in payload
    assert '"kind":"done"' in payload


def test_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKENS", "k")
    server = ChatServer(
        agent_factory=_agent_factory,
        history_store=InMemoryChatHistory(),
        auth=EnvBearerAuth("API_TOKENS"),
        rate_limit_per_session_per_minute=1,
    )
    client = TestClient(server.app)
    sid = client.post("/sessions", json={}, headers={"Authorization": "Bearer k"}).json()["id"]
    headers = {"Authorization": "Bearer k"}
    r1 = client.post(f"/sessions/{sid}/messages", json={"content": "a"}, headers=headers)
    assert r1.status_code == 200
    r2 = client.post(f"/sessions/{sid}/messages", json={"content": "b"}, headers=headers)
    assert r2.status_code == 429


def test_websocket_round_trip(client: TestClient) -> None:
    sid = client.post("/sessions", json={}, headers=_auth()).json()["id"]
    with client.websocket_connect(
        f"/sessions/{sid}/ws",
        headers=_auth(),
    ) as ws:
        ws.send_text('{"content": "hi"}')
        seen_done = False
        for _ in range(10):
            data = ws.receive_text()
            if '"kind":"done"' in data:
                seen_done = True
                break
        assert seen_done


@pytest.mark.parametrize("missing_var", ["MISSING_TOKENS_VAR_FOR_TEST"])
def test_empty_env_var_rejects_all_tokens(
    missing_var: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(missing_var, raising=False)
    assert os.environ.get(missing_var) is None
    auth = EnvBearerAuth(missing_var)
    server = ChatServer(
        agent_factory=_agent_factory,
        history_store=InMemoryChatHistory(),
        auth=auth,
    )
    client = TestClient(server.app)
    r = client.post("/sessions", json={}, headers={"Authorization": "Bearer anything"})
    assert r.status_code == 401
