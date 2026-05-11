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

from collections.abc import Iterable
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


class _SDKServerRunner:  # pragma: no cover — exercised only with `mcp` installed
    """Production wrapper around `mcp.server.Server`.

    Real transport wiring is deferred until the framework's first
    integration test against a live MCP client; the contract
    methods raise an actionable error until then.
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

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Any,
    ) -> None:
        del name, description, input_schema, handler
        msg = (
            "Production MCP server not implemented yet. Inject a fake "
            "`MCPServerRunner` via `MCPServer(runner=...)`."
        )
        raise ModuleError(msg)

    async def serve(self) -> None:
        msg = "Production MCP server not implemented yet."
        raise ModuleError(msg)

    async def stop(self) -> None:
        return


__all__ = ["MCPServer"]
