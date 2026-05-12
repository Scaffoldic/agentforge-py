"""`MCPServerClient` — connect to an upstream MCP server (feat-013).

Three transports per spec §4.5: `stdio` (spawn the server as a
subprocess and speak the line-delimited JSON-RPC dialect), `http`,
and `sse`. The actual transport setup is delegated to the official
`mcp` SDK; this module wraps the SDK behind the `MCPClientRunner`
protocol so tests don't need it installed.
"""

from __future__ import annotations

from agentforge_core.contracts.tool import Tool
from agentforge_core.production.exceptions import ModuleError

from agentforge_mcp._runner import MCPClientRunner, MCPToolDescriptor
from agentforge_mcp.adapter import build_adapter


class MCPServerClient:
    """Connects to a single upstream MCP server and adapts its
    tools.

    Use the `from_stdio` / `from_http` / `from_sse` factories;
    the bare constructor takes a pre-built runner (for tests).
    """

    def __init__(
        self,
        *,
        name: str,
        runner: MCPClientRunner,
        tool_filter: tuple[str, ...] = (),
    ) -> None:
        self._name = name
        self._runner = runner
        self._tool_filter = tuple(tool_filter)

    @property
    def name(self) -> str:
        return self._name

    @classmethod
    async def from_stdio(
        cls,
        *,
        name: str,
        command: str,
        env: dict[str, str] | None = None,
        tool_filter: tuple[str, ...] = (),
        timeout_s: float = 30.0,
    ) -> MCPServerClient:
        """Spawn the MCP server as a subprocess and connect via stdio.

        `command` is split shell-style (e.g.
        `"npx -y @modelcontextprotocol/server-filesystem /work"`).
        `env` extends the spawned process's environment.
        """
        runner = await _build_stdio_runner(name=name, command=command, env=env, timeout_s=timeout_s)
        return cls(name=name, runner=runner, tool_filter=tool_filter)

    @classmethod
    async def from_http(
        cls,
        *,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
        tool_filter: tuple[str, ...] = (),
        timeout_s: float = 30.0,
    ) -> MCPServerClient:
        """Connect to a hosted MCP server over HTTP."""
        runner = await _build_http_runner(
            name=name,
            url=url,
            headers=headers,
            timeout_s=timeout_s,
            transport="http",
        )
        return cls(name=name, runner=runner, tool_filter=tool_filter)

    @classmethod
    async def from_sse(
        cls,
        *,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
        tool_filter: tuple[str, ...] = (),
        timeout_s: float = 30.0,
    ) -> MCPServerClient:
        """Connect over Server-Sent Events."""
        runner = await _build_http_runner(
            name=name,
            url=url,
            headers=headers,
            timeout_s=timeout_s,
            transport="sse",
        )
        return cls(name=name, runner=runner, tool_filter=tool_filter)

    async def discover_tools(self) -> list[Tool]:
        """Fetch the server's tool catalogue + adapt each into a
        framework-shaped Tool."""
        descriptors = await self._runner.list_tools()
        kept = self._apply_filter(descriptors)
        return [
            build_adapter(self._runner, descriptor, server_name=self._name) for descriptor in kept
        ]

    async def close(self) -> None:
        await self._runner.close()

    def _apply_filter(self, descriptors: list[MCPToolDescriptor]) -> list[MCPToolDescriptor]:
        if not self._tool_filter:
            return list(descriptors)
        keep = set(self._tool_filter)
        return [d for d in descriptors if d.name in keep]


async def _build_stdio_runner(
    *,
    name: str,
    command: str,
    env: dict[str, str] | None,
    timeout_s: float,
) -> MCPClientRunner:
    """Production stdio runner — lazy-imports `mcp`.

    Tests skip this entirely by injecting a fake runner via the
    bare constructor.
    """
    try:
        from mcp import ClientSession  # noqa: PLC0415
        from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: PLC0415
    except ImportError as exc:
        msg = "mcp SDK is not installed. Install via `pip install mcp` to consume MCP servers."
        raise ModuleError(msg) from exc
    parts = command.split()
    if not parts:
        msg = f"MCP server {name!r}: command is empty."
        raise ModuleError(msg)
    params = StdioServerParameters(
        command=parts[0],
        args=parts[1:],
        env=dict(env or {}),
    )
    return _SDKClientRunner(
        session_factory=lambda: stdio_client(params),
        session_cls=ClientSession,
        timeout_s=timeout_s,
    )


async def _build_http_runner(
    *,
    name: str,
    url: str,
    headers: dict[str, str] | None,
    timeout_s: float,
    transport: str,
) -> MCPClientRunner:
    """Production HTTP / SSE runner — lazy-imports `mcp`."""
    try:
        from mcp import ClientSession  # noqa: PLC0415

        if transport == "sse":
            from mcp.client.sse import sse_client as connect  # noqa: PLC0415
        else:
            from mcp.client.streamable_http import (  # noqa: PLC0415
                streamablehttp_client as connect,
            )
    except ImportError as exc:
        msg = (
            f"mcp SDK is not installed. Install via `pip install mcp` to "
            f"connect to MCP server {name!r} over {transport}."
        )
        raise ModuleError(msg) from exc
    return _SDKClientRunner(
        session_factory=lambda: connect(url, headers=dict(headers or {})),
        session_cls=ClientSession,
        timeout_s=timeout_s,
    )


class _SDKClientRunner:  # pragma: no cover — exercised only with `mcp` installed (live tests)
    """Wraps the upstream `mcp.ClientSession`. Live integration
    only; unit tests inject a fake runner.

    Holds the session and the transport context manager open for
    the lifetime of the runner; `close()` releases both. Live
    transport wiring is deferred until the framework's first
    integration test against a real MCP server; until then this
    raises an actionable error from each contract method.
    """

    def __init__(
        self,
        *,
        session_factory: object,
        session_cls: object,
        timeout_s: float,
    ) -> None:
        self._session_factory = session_factory
        self._session_cls = session_cls
        self._timeout_s = timeout_s
        self._session: object | None = None

    async def list_tools(self) -> list[MCPToolDescriptor]:
        msg = (
            "Production MCP runner not implemented yet. Inject a "
            "fake `MCPClientRunner` via `MCPServerClient(runner=...)`."
        )
        raise ModuleError(msg)

    async def call_tool(self, name: str, arguments: dict[str, object]) -> str:
        del name, arguments
        msg = (
            "Production MCP runner not implemented yet. Inject a "
            "fake `MCPClientRunner` via `MCPServerClient(runner=...)`."
        )
        raise ModuleError(msg)

    async def close(self) -> None:
        return


__all__ = ["MCPServerClient"]
