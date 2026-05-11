"""Internal MCP runner protocol (feat-013).

`MCPRunner` is the thin slice of `mcp.ClientSession` /
`mcp.server.Server` we depend on. Tests inject a fake runner so
the upstream `mcp` package does not need to be installed in the
test environment.

Production runners lazy-import `mcp` so the package can be
installed without the SDK present (the SDK is the user's choice
of stdio vs. HTTP / SSE server type).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class MCPToolDescriptor:
    """One tool advertised by an MCP server.

    Mirrors the `mcp.types.Tool` shape but pinned to what we
    consume: name, description, JSON schema for inputs.
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


class MCPClientRunner(Protocol):
    """Subset of `mcp.ClientSession` we depend on.

    `list_tools` is called once at session start to fetch the
    server's tool catalogue. `call_tool` runs a single
    invocation and returns the textual result (we treat MCP
    `content` blobs as their concatenated text representation).
    """

    async def list_tools(self) -> list[MCPToolDescriptor]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str: ...

    async def close(self) -> None: ...


class MCPServerRunner(Protocol):
    """Subset of `mcp.server.Server` we depend on.

    `register_tool(name, description, input_schema, handler)`
    wires a tool into the server; `serve` blocks until the
    server is stopped.
    """

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Any,
    ) -> None: ...

    async def serve(self) -> None: ...

    async def stop(self) -> None: ...


__all__ = [
    "MCPClientRunner",
    "MCPServerRunner",
    "MCPToolDescriptor",
]
