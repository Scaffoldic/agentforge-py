"""Live MCP integration test (feat-013 v0.2).

Spawns a tiny echo MCP server as a subprocess (the script in
`_echo_server.py`), connects via `MCPServerClient.from_stdio`,
round-trips `list_tools` + `call_tool`, and tears down. Verifies
the production `_SDKClientRunner` against the real upstream
`mcp` SDK.

Gated by `@pytest.mark.live`; the default pre-commit + CI gate
skips this with `-m "not live"`. Run explicitly with:

    uv run pytest -m live packages/agentforge-mcp/tests/integration/
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import sys
from pathlib import Path
from typing import Any

import pytest
from agentforge_core.contracts.tool import Tool
from agentforge_mcp import MCPServer, MCPServerClient
from pydantic import BaseModel


@pytest.mark.live
@pytest.mark.asyncio
async def test_stdio_roundtrip_against_real_mcp_server() -> None:
    echo_script = Path(__file__).with_name("_echo_server.py").resolve()
    command = f"{sys.executable} {echo_script}"

    client = await MCPServerClient.from_stdio(name="echo", command=command)
    try:
        tools = await client.discover_tools()
        assert len(tools) == 1
        tool = tools[0]
        # Tools come back with server-name-prefixed names (double-underscore
        # separator — legal under every provider's tool-name charset).
        assert type(tool).name == "echo__echo"
        # Invoke through the adapter — the runner routes to the
        # subprocess and the echo server returns the input unchanged.
        result = await tool.run(text="hello mcp")
        assert "hello mcp" in result
    finally:
        await client.close()


class _HttpEchoInput(BaseModel):
    text: str


class _HttpEcho(Tool):
    name = "http_echo"
    description = "Echo the input text."
    input_schema = _HttpEchoInput

    async def run(self, **kwargs: Any) -> str:
        return f"echoed:{kwargs.get('text', '')}"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _wait_until_listening(host: str, port: int, *, timeout_s: float = 10.0) -> None:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        try:
            _, writer = await asyncio.open_connection(host, port)
        except OSError:
            await asyncio.sleep(0.1)
        else:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            return
    raise TimeoutError(f"MCP HTTP server on {host}:{port} did not start in {timeout_s}s")


@pytest.mark.live
@pytest.mark.asyncio
async def test_http_roundtrip_against_real_mcp_server() -> None:
    """enh-001: an HTTP MCPServer serves tools and a client round-trips
    list + call over streamable-HTTP."""
    host, port = "127.0.0.1", _free_port()
    server = MCPServer.from_http(tools=[_HttpEcho()], host=host, port=port)
    serve_task = asyncio.create_task(server.serve())
    try:
        await _wait_until_listening(host, port)
        client = await MCPServerClient.from_http(name="echo", url=f"http://{host}:{port}/mcp")
        try:
            tools = await client.discover_tools()
            assert [type(t).name for t in tools] == ["echo__http_echo"]
            result = await tools[0].run(text="hello http")
            assert "hello http" in result
        finally:
            await client.close()
    finally:
        # stop() signals uvicorn to exit; let it drain so its sockets
        # close cleanly before falling back to cancellation.
        await server.stop()
        with contextlib.suppress(TimeoutError, asyncio.CancelledError, Exception):
            await asyncio.wait_for(serve_task, timeout=5.0)
        if not serve_task.done():
            serve_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await serve_task
