"""`MCPBridge` — orchestrate consume + expose for an Agent (feat-013).

Wired by the resolver from `modules.protocols.mcp.config`. Spawns
each configured `MCPServerClient`, collects their tools into one
list, and optionally starts an `MCPServer` exposing this agent's
own tools.

Lifecycle: `await bridge.start()` opens every client (and the
optional server). `await bridge.close()` tears everything down.
`bridge.tools` is the merged Tool catalogue ready to pass to
`Agent(tools=...)`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from agentforge_core.contracts.tool import Tool

from agentforge_mcp.client import MCPServerClient
from agentforge_mcp.server import MCPServer


class MCPBridge:
    """Per-agent MCP orchestrator.

    Holds a list of `MCPServerClient`s and (optionally) one
    `MCPServer` for the expose path. `start()` populates
    `bridge.tools`; `close()` tears down every connection and
    stops the exposed server if any.
    """

    def __init__(
        self,
        *,
        clients: Iterable[MCPServerClient] = (),
        server: MCPServer | None = None,
        client_specs: Iterable[dict[str, Any]] = (),
    ) -> None:
        self._clients = list(clients)
        # Deferred client entries from `from_config`. Materialised into
        # live `MCPServerClient`s inside `start()` (async) so no event
        # loop is driven at construction time (bug-014).
        self._client_specs = [dict(spec) for spec in client_specs]
        self._server = server
        self._tools: list[Tool] = []
        self._serve_task: asyncio.Task[None] | None = None

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> MCPBridge:
        """Build a bridge from the parsed `modules.protocols.mcp.config`
        block.

        Pure data — no transports are opened and no event loop is
        driven here. The server entries are stashed as ``client_specs``
        and materialised inside ``start()`` (which is async and safe to
        call from within a running loop). Tests typically bypass this
        and inject pre-built clients via ``__init__``.
        """
        specs = list(config.get("servers", []) or [])
        server: MCPServer | None = None
        expose = config.get("expose") or {}
        if expose.get("enabled"):
            # The agent's own tools aren't known at config-load time;
            # call `bridge.attach_local_tools(tools)` after Agent
            # construction. The server is built here so the transport
            # spec lives with the bridge.
            server = _server_placeholder(expose)
        return cls(client_specs=specs, server=server)

    @property
    def tools(self) -> list[Tool]:
        """Merged Tool catalogue (populated by `start`)."""
        return list(self._tools)

    def attach_local_tools(self, tools: Iterable[Tool]) -> None:
        """Inject the agent's own tools into the exposed server.

        No-op when this bridge has no `expose` server configured. Call
        after `Agent` construction (when the tool list is known) and
        before `start()`.
        """
        if self._server is not None:
            self._server.set_tools(tools)

    async def start(self) -> None:
        """Materialise deferred clients, open every client, discover
        their tools, and (optionally) start the exposed server."""
        for spec in self._client_specs:
            self._clients.append(await _client_from_entry_async(spec))
        self._client_specs = []
        for client in self._clients:
            self._tools.extend(await client.discover_tools())
        if self._server is not None:
            self._server.register_tools()
            self._serve_task = asyncio.create_task(self._server.serve())

    async def close(self) -> None:
        if self._server is not None:
            await self._server.stop()
        if self._serve_task is not None:
            self._serve_task.cancel()
            with _Suppress(asyncio.CancelledError):
                await self._serve_task
        for client in self._clients:
            await client.close()


async def _client_from_entry_async(
    entry: dict[str, Any],
) -> MCPServerClient:  # pragma: no cover — live wiring
    """Construct an `MCPServerClient` from a config entry.

    Awaits the async transport factory directly, so it must be called
    from within an event loop (it is — `start()` is async). Excluded
    from coverage because it depends on the upstream `mcp` SDK; tests
    inject pre-built clients into `MCPBridge` or monkeypatch this
    function.
    """
    transport = entry.get("transport", "stdio")
    name = str(entry["name"])
    tool_filter = tuple(entry.get("tool_filter") or ())
    timeout_s = float(entry.get("timeout_s", 30.0))
    if transport == "stdio":
        return await MCPServerClient.from_stdio(
            name=name,
            command=_command_str(entry["command"]),
            env=dict(entry.get("env") or {}),
            tool_filter=tool_filter,
            timeout_s=timeout_s,
        )
    if transport in {"http", "sse"}:
        factory = MCPServerClient.from_http if transport == "http" else MCPServerClient.from_sse
        return await factory(
            name=name,
            url=str(entry["url"]),
            headers=dict(entry.get("headers") or {}),
            tool_filter=tool_filter,
            timeout_s=timeout_s,
        )
    msg = f"MCP server {name!r}: unsupported transport {transport!r}."
    raise ValueError(msg)


def _command_str(command: Any) -> str:
    """Normalise a `command:` entry to the shell string `from_stdio`
    expects. YAML may give a list (``["uv", "run", "x"]``) or a plain
    string (``"uv run x"``); both collapse to a space-joined string."""
    if isinstance(command, (list, tuple)):
        return " ".join(str(part) for part in command)
    return str(command)


def _server_placeholder(expose: dict[str, Any]) -> MCPServer:  # pragma: no cover — live wiring
    """Build the exposed-server side from the `expose` block.

    Tools are wired in later via `attach_local_tools` once the
    `Agent` knows its own tool list.
    """
    transport = expose.get("transport", "stdio")
    allowed = tuple(expose.get("tools") or ())
    if transport == "stdio":
        return MCPServer.from_stdio(tools=[], allowed=allowed)
    if transport == "http":
        return MCPServer.from_http(tools=[], allowed=allowed)
    msg = f"unsupported expose transport {transport!r}; expected 'stdio' or 'http'."
    raise ValueError(msg)


class _Suppress:
    """`contextlib.suppress` re-implementation that's mypy-friendly."""

    def __init__(self, *exc: type[BaseException]) -> None:
        self._exc = exc

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> bool:
        del exc, tb
        return exc_type is not None and issubclass(exc_type, self._exc)


__all__ = ["MCPBridge"]
