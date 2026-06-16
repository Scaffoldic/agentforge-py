"""Tests for `MCPServer` (feat-013 chunk 3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from agentforge_core.contracts.tool import Tool
from agentforge_mcp import MCPServer
from pydantic import BaseModel


@dataclass
class MCPFakeServerRunner:
    """Inline fake — records registrations, simulates serve/stop."""

    registered: list[dict[str, Any]] = field(default_factory=list)
    served: bool = False
    stopped: bool = False

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Any,
    ) -> None:
        self.registered.append(
            {
                "name": name,
                "description": description,
                "schema": input_schema,
                "handler": handler,
            }
        )

    async def serve(self) -> None:
        self.served = True

    async def stop(self) -> None:
        self.stopped = True


class _Inp(BaseModel):
    text: str


class _Echo(Tool):
    name = "lookup_user"
    description = "Look up user by id."
    input_schema = _Inp

    async def run(self, **kwargs: Any) -> str:
        return f"user:{kwargs.get('text', '')}"


class _Internal(Tool):
    name = "create_ticket"
    description = "Create an internal ticket."
    input_schema = _Inp

    async def run(self, **kwargs: Any) -> str:
        del kwargs
        return "ticket:42"


class _Hidden(Tool):
    name = "private"
    description = "Should not be exposed."
    input_schema = _Inp

    async def run(self, **kwargs: Any) -> str:
        del kwargs
        return ""


def test_register_tools_publishes_each() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer(tools=[_Echo(), _Internal()], runner=runner)
    count = server.register_tools()
    assert count == 2
    names = [r["name"] for r in runner.registered]
    assert names == ["lookup_user", "create_ticket"]


def test_allowed_whitelist_restricts_exposure() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer(
        tools=[_Echo(), _Internal(), _Hidden()],
        runner=runner,
        allowed=("lookup_user", "create_ticket"),
    )
    count = server.register_tools()
    assert count == 2
    assert "private" not in {r["name"] for r in runner.registered}


@pytest.mark.asyncio
async def test_handler_round_trips_through_tool() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer(tools=[_Echo()], runner=runner)
    server.register_tools()
    [registration] = runner.registered
    handler = registration["handler"]
    out = await handler({"text": "alice"})
    assert out == "user:alice"


@pytest.mark.asyncio
async def test_serve_and_stop_delegate_to_runner() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer(tools=[_Echo()], runner=runner)
    await server.serve()
    assert runner.served
    await server.stop()
    assert runner.stopped


def test_register_tools_emits_pydantic_schema_dict() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer(tools=[_Echo()], runner=runner)
    server.register_tools()
    schema = runner.registered[0]["schema"]
    assert schema["type"] == "object"
    assert "text" in schema["properties"]


def test_from_stdio_auto_registers_tools() -> None:
    """bug-013: from_stdio publishes tools up front, so calling serve()
    straight after no longer yields an empty ListTools."""
    runner = MCPFakeServerRunner()
    server = MCPServer.from_stdio(tools=[_Echo()], runner=runner)
    assert [r["name"] for r in runner.registered] == ["lookup_user"]
    # Idempotent: an explicit second call registers nothing more.
    assert server.register_tools() == 0
    assert len(runner.registered) == 1


def test_from_http_auto_registers_tools() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer.from_http(tools=[_Echo()], runner=runner)
    assert [r["name"] for r in runner.registered] == ["lookup_user"]
    assert server.register_tools() == 0


def test_set_tools_re_arms_registration() -> None:
    """attach_local_tools → set_tools must let the next register_tools
    publish the injected set (the MCPBridge expose path)."""
    runner = MCPFakeServerRunner()
    server = MCPServer.from_stdio(tools=[], runner=runner)
    assert runner.registered == []  # empty placeholder registers nothing
    server.set_tools([_Echo()])
    assert server.register_tools() == 1
    assert [r["name"] for r in runner.registered] == ["lookup_user"]


# ---- enh-003: HTTP middleware seam ----


def _ok_asgi_app() -> Any:
    """A trivial ASGI handler standing in for the streamable-HTTP route."""
    from starlette.responses import PlainTextResponse  # noqa: PLC0415

    async def _app(scope: Any, receive: Any, send: Any) -> None:
        await PlainTextResponse("ok")(scope, receive, send)

    return _app


def test_build_http_app_applies_caller_middleware_as_auth_gate() -> None:
    """enh-003: a caller-supplied Starlette middleware must wrap the app,
    so an agent can put a bearer-token gate in front of the otherwise-open
    MCP HTTP transport without re-implementing the serve path."""
    pytest.importorskip("starlette")
    from agentforge_mcp.server import _build_http_app  # noqa: PLC0415
    from starlette.middleware import Middleware  # noqa: PLC0415
    from starlette.middleware.base import BaseHTTPMiddleware  # noqa: PLC0415
    from starlette.responses import PlainTextResponse  # noqa: PLC0415
    from starlette.testclient import TestClient  # noqa: PLC0415

    class _BearerGate(BaseHTTPMiddleware):
        def __init__(self, app: Any, *, token: str) -> None:
            super().__init__(app)
            self._token = token

        async def dispatch(self, request: Any, call_next: Any) -> Any:
            if request.headers.get("authorization") != f"Bearer {self._token}":
                return PlainTextResponse("unauthorized", status_code=401)
            return await call_next(request)

    app = _build_http_app(
        _ok_asgi_app(),
        lifespan=None,
        middleware=[Middleware(_BearerGate, token="s3cret")],
    )
    client = TestClient(app)

    assert client.get("/mcp").status_code == 401  # no token → gated
    authed = client.get("/mcp", headers={"Authorization": "Bearer s3cret"})
    assert authed.status_code == 200  # correct token → reaches the route
    assert authed.text == "ok"


def test_build_http_app_without_middleware_reaches_route() -> None:
    """No middleware → the mounted ASGI route is reached directly."""
    pytest.importorskip("starlette")
    from agentforge_mcp.server import _build_http_app  # noqa: PLC0415
    from starlette.testclient import TestClient  # noqa: PLC0415

    app = _build_http_app(_ok_asgi_app(), lifespan=None, middleware=None)
    assert TestClient(app).get("/mcp").status_code == 200
