"""`MCPServer` — expose AgentForge `Tool` instances as MCP (feat-013).

When `modules.protocols.mcp.expose.enabled` is set, the agent runs
an MCP server alongside so other clients (Claude Desktop, Cursor,
another AgentForge agent) can call into its tools.

`MCPServer.from_stdio(tools, allowed)` / `from_http(...)` lazy-
import the upstream SDK. Tests inject a fake `MCPServerRunner`
via the bare constructor and drive
`server.register_tools()` + `server.serve()` without the SDK.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from agentforge_core.contracts.tool import Tool
from agentforge_core.production.exceptions import ModuleError

from agentforge_mcp._runner import MCPServerRunner


class MCPServer:
    """Exposes a set of `Tool` instances as an MCP server.

    Construction:
    - `MCPServer(tools, runner, allowed=...)` — direct (tests).
    - `MCPServer.from_stdio(tools, allowed)` / `from_http(...)` —
      production; lazy-imports `mcp`.
    """

    def __init__(
        self,
        *,
        tools: Iterable[Tool],
        runner: MCPServerRunner,
        allowed: tuple[str, ...] = (),
    ) -> None:
        self._tools = list(tools)
        self._runner = runner
        self._allowed = set(allowed)

    @classmethod
    def from_stdio(
        cls,
        *,
        tools: Iterable[Tool],
        allowed: tuple[str, ...] = (),
        server_name: str = "agentforge",
    ) -> MCPServer:
        runner = _build_stdio_server_runner(server_name=server_name)
        return cls(tools=tools, runner=runner, allowed=allowed)

    @classmethod
    def from_http(
        cls,
        *,
        tools: Iterable[Tool],
        host: str = "127.0.0.1",
        port: int = 8765,
        allowed: tuple[str, ...] = (),
        server_name: str = "agentforge",
    ) -> MCPServer:
        runner = _build_http_server_runner(
            server_name=server_name,
            host=host,
            port=port,
        )
        return cls(tools=tools, runner=runner, allowed=allowed)

    def set_tools(self, tools: Iterable[Tool]) -> None:
        """Replace the tool set to expose.

        Used by `MCPBridge.attach_local_tools` to inject the agent's
        own tools after construction (the agent's tool list isn't known
        at config-load time). Call before `register_tools()` / `serve()`.
        """
        self._tools = list(tools)

    def register_tools(self) -> int:
        """Register each whitelisted tool with the underlying runner.

        Returns the count of registrations. A tool whose name is
        not in `allowed` (when `allowed` is non-empty) is skipped
        with no error — the contract is allowlist, not error.
        """
        count = 0
        for tool in self._tools:
            tool_name = type(tool).name
            if self._allowed and tool_name not in self._allowed:
                continue
            self._runner.register_tool(
                tool_name,
                type(tool).description,
                type(tool).input_schema.model_json_schema(),
                _make_handler(tool),
            )
            count += 1
        return count

    async def serve(self) -> None:
        """Block on the underlying runner until `stop()` is called."""
        await self._runner.serve()

    async def stop(self) -> None:
        await self._runner.stop()


def _make_handler(tool: Tool) -> Any:
    """Build a per-tool async handler bound to the agent's `Tool`."""

    async def _handler(arguments: dict[str, Any]) -> str:
        result = await tool.run(**arguments)
        return str(result) if not isinstance(result, str) else result

    return _handler


def _build_stdio_server_runner(  # pragma: no cover — exercised only with `mcp` installed
    *,
    server_name: str,
) -> MCPServerRunner:
    try:
        from mcp.server import Server  # noqa: PLC0415
        from mcp.server.stdio import stdio_server  # noqa: PLC0415, F401
    except ImportError as exc:
        msg = (
            "mcp SDK is not installed. Install via `pip install mcp` to "
            "expose tools as an MCP stdio server."
        )
        raise ModuleError(msg) from exc
    return _SDKServerRunner(server=Server(server_name), transport="stdio")


def _build_http_server_runner(  # pragma: no cover — exercised only with `mcp` installed
    *,
    server_name: str,
    host: str,
    port: int,
) -> MCPServerRunner:
    try:
        from mcp.server import Server  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "mcp SDK is not installed. Install via `pip install mcp` to "
            "expose tools as an MCP HTTP server."
        )
        raise ModuleError(msg) from exc
    return _SDKServerRunner(server=Server(server_name), transport="http", host=host, port=port)


@dataclass
class _RegisteredTool:
    """One tool registered with the MCP server runner."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    handler: Callable[[dict[str, Any]], Awaitable[str]] | None = None


class _SDKServerRunner:  # pragma: no cover — only with `mcp` SDK + `-m live`
    """Production wrapper around `mcp.server.Server`.

    `register_tool(...)` collects each registration into an
    in-memory registry. On `serve()` we apply the SDK's
    decorator-based registration pattern over the accumulated
    registry: one `@server.list_tools()` handler returns every
    registered descriptor; one `@server.call_tool()` handler
    dispatches by name into the per-tool handler. Then we open
    the configured transport (stdio for v0.2; HTTP / SSE is a
    follow-up — see spec §10) and await `server.run(...)`.
    `stop()` cancels the serve task.
    """

    def __init__(
        self,
        *,
        server: Any,
        transport: str,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self._server = server
        self._transport = transport
        self._host = host
        self._port = port
        self._tools: dict[str, _RegisteredTool] = {}
        self._serve_task: asyncio.Task[None] | None = None

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Any,
    ) -> None:
        self._tools[name] = _RegisteredTool(
            name=name,
            description=description,
            input_schema=dict(input_schema or {}),
            handler=handler,
        )

    async def serve(self) -> None:
        if self._transport != "stdio":
            # HTTP / SSE server transport ships in a v0.2.1 follow-up
            # — needs the streamable-http manager + uvicorn wiring.
            # Stdio is the v0.2 deliverable.
            msg = (
                f"MCP server transport {self._transport!r} is not yet "
                "implemented. Use transport='stdio' for v0.2."
            )
            raise ModuleError(msg)
        from mcp.server.stdio import stdio_server  # noqa: PLC0415
        from mcp.types import TextContent  # noqa: PLC0415
        from mcp.types import Tool as MCPTool  # noqa: PLC0415

        registered = self._tools

        @self._server.list_tools()  # type: ignore[untyped-decorator]
        async def _handle_list_tools() -> list[MCPTool]:  # type: ignore[no-any-unimported]
            return [
                MCPTool(
                    name=t.name,
                    description=t.description,
                    inputSchema=t.input_schema,
                )
                for t in registered.values()
            ]

        @self._server.call_tool()  # type: ignore[untyped-decorator]
        async def _handle_call_tool(  # type: ignore[no-any-unimported]
            name: str, arguments: dict[str, Any]
        ) -> list[TextContent]:
            tool = registered.get(name)
            if tool is None or tool.handler is None:
                msg = f"MCP server: unknown tool {name!r}"
                raise ModuleError(msg)
            result_text = await tool.handler(arguments)
            return [TextContent(type="text", text=result_text)]

        options = self._server.create_initialization_options()
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(read_stream, write_stream, options)

    async def stop(self) -> None:
        if self._serve_task is not None and not self._serve_task.done():
            self._serve_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._serve_task
        self._serve_task = None


__all__ = ["MCPServer"]
