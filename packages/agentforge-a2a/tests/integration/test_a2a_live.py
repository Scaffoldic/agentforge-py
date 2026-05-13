"""Live A2A integration test (feat-014 v0.3).

Spawns a real `uvicorn.Server` on a random localhost port,
points a real `_HTTPXClientRunner` at it, and round-trips:

1. `agent_call(...)` — unary `POST /a2a/v1/calls`.
2. `discover_peer(...)` — `GET /a2a/v1/info`.
3. `agent_call_stream(...)` — SSE `POST /a2a/v1/calls/stream`
   exercising per-token streaming via a strategy that overrides
   `ReasoningStrategy.stream()`.

Gated by `@pytest.mark.live` so the default unit gate skips it.
Run explicitly with:

    uv run pytest -m live packages/agentforge-a2a/tests/integration/
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
import uvicorn
from agentforge.agent import Agent
from agentforge.runtime import RUNTIME_KEY
from agentforge_a2a import (
    A2APeer,
    A2AServer,
    BearerAuth,
    agent_call,
    agent_call_stream,
    discover_peer,
)
from agentforge_a2a._runner import _HTTPXClientRunner
from agentforge_a2a.values import A2AEndpointConfig
from agentforge_core.contracts.auth import AuthPolicy
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.auth import Principal
from agentforge_core.values.chat import StreamingEvent
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolSpec,
)
from agentforge_core.values.state import AgentState, Step


class _PerTokenStrategy(ReasoningStrategy):
    """Overrides both `run` (for unary callers) and `stream` (for
    per-token A2A streaming). The streamed sequence is three text
    tokens, a tool call, a tool result, and a terminal done — the
    canonical demonstration of the v0.3 per-token contract."""

    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.0)
        state.steps.append(Step(iteration=0, kind="synthesize", content="Hello, world!"))
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[StreamingEvent]:
        runtime = state.metadata.get(RUNTIME_KEY)
        if runtime is not None:
            runtime.budget.commit(0.0)
        for tok in ("Hello, ", "world", "!"):
            yield StreamingEvent(kind="text", content=tok)
        yield StreamingEvent(kind="tool_call", content={"name": "noop", "arguments": {}})
        yield StreamingEvent(kind="tool_result", content={"output": "ok"})
        state.steps.append(Step(iteration=0, kind="synthesize", content="Hello, world!"))
        yield StreamingEvent(
            kind="done",
            content={"run_id": state.run_id, "cost_usd": 0.0, "output": "Hello, world!"},
        )


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


class _StaticBearerAuth(AuthPolicy):
    """Accepts exactly one bearer token."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def authenticate(self, token: str | None) -> Principal | None:
        if token != self._token:
            return None
        return Principal(id="live-test")


def _build_agent() -> Agent:
    return Agent(model=_FakeLLM(), strategy=_PerTokenStrategy())


def _build_server(*, token: str = "live-tok") -> A2AServer:
    return A2AServer(
        agent=_build_agent(),
        auth=_StaticBearerAuth(token),
        endpoints=["verify"],
        endpoint_descriptors=[
            A2AEndpointConfig(
                name="verify",
                description="Live integration verifier",
                accepts={"type": "object", "properties": {"k": {"type": "string"}}},
            )
        ],
        server_name="live-test",
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class _SpawnedServer:
    base_url: str
    calls_url: str


@contextlib.asynccontextmanager
async def _spawn_server(server: A2AServer) -> AsyncIterator[_SpawnedServer]:
    port = _free_port()
    config = uvicorn.Config(
        server.app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="off",
    )
    uv_server = uvicorn.Server(config)
    # uvicorn's default install_signal_handlers() needs the main thread;
    # the pytest worker loop may not have it. No-op the call so startup
    # proceeds to the socket bind.
    uv_server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    task = asyncio.create_task(uv_server.serve())
    for _ in range(200):
        if uv_server.started:
            break
        await asyncio.sleep(0.02)
    if not uv_server.started:
        uv_server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(task, timeout=5.0)
        msg = "uvicorn test server failed to start within 4s"
        raise RuntimeError(msg)
    await asyncio.sleep(0.05)
    base_url = f"http://127.0.0.1:{port}"
    try:
        yield _SpawnedServer(base_url=base_url, calls_url=f"{base_url}/a2a/v1/calls")
    finally:
        uv_server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(task, timeout=5.0)


@pytest.mark.live
@pytest.mark.asyncio
async def test_unary_call_round_trip() -> None:
    server = _build_server()
    runner = _HTTPXClientRunner()
    try:
        async with _spawn_server(server) as bound:
            peer = A2APeer(
                name="live",
                url=bound.calls_url,
                auth=BearerAuth("live-tok"),
                runner=runner,
            )
            response = await agent_call(
                "live:verify",
                {"k": "v"},
                peers={"live": peer},
                timeout_s=10.0,
            )
            assert response.run_id
            assert response.cost_usd >= 0.0
    finally:
        await runner.close()


@pytest.mark.live
@pytest.mark.asyncio
async def test_discover_round_trip() -> None:
    server = _build_server()
    runner = _HTTPXClientRunner()
    try:
        async with _spawn_server(server) as bound:
            peer = A2APeer(
                name="live",
                url=bound.calls_url,
                auth=BearerAuth("live-tok"),
                runner=runner,
            )
            info = await discover_peer(peer, timeout_s=10.0)
            assert info.server_name == "live-test"
            assert {e.name for e in info.endpoints} == {"verify"}
            verify = info.endpoints[0]
            assert verify.description == "Live integration verifier"
            assert verify.input_schema["type"] == "object"
    finally:
        await runner.close()


@pytest.mark.live
@pytest.mark.asyncio
async def test_stream_round_trip() -> None:
    server = _build_server()
    runner = _HTTPXClientRunner()
    try:
        async with _spawn_server(server) as bound:
            peer = A2APeer(
                name="live",
                url=bound.calls_url,
                auth=BearerAuth("live-tok"),
                runner=runner,
            )
            chunks = [
                chunk
                async for chunk in agent_call_stream(
                    "live:verify",
                    {"k": "v"},
                    peers={"live": peer},
                    timeout_s=15.0,
                )
            ]
            kinds = [c.kind for c in chunks]
            # v0.3 per-token contract: three `text` tokens, then one
            # `tool_call` and one `tool_result`, then the canonical
            # `done` emitted by the server (carrying the assembled
            # output + cost + run_id).
            assert kinds == [
                "text",
                "text",
                "text",
                "tool_call",
                "tool_result",
                "done",
            ]
            text_tokens = [c.content for c in chunks if c.kind == "text"]
            assert text_tokens == ["Hello, ", "world", "!"]
            done = chunks[-1]
            assert done.run_id is not None
            assert isinstance(done.content, dict)
            assert done.content["output"] == "Hello, world!"
            assert done.content["cost_usd"] == 0.0
    finally:
        await runner.close()
