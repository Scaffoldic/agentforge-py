"""A tiny MCP server that exposes one `echo` tool.

Used as the subprocess target for the live integration test in
`test_mcp_live.py`. Stays minimal: register one tool whose handler
returns whatever `text` argument it was called with. Stdio
transport so the client can spawn this script directly.

Invocation (from the test):

    python -m agentforge_mcp_tests_integration._echo_server

Or:

    python -c "from agentforge_mcp_tests_integration._echo_server import main; main()"

The test resolves an absolute path to this file so subprocess
launch is reliable regardless of how tests are invoked.
"""

from __future__ import annotations

import asyncio
from typing import Any


async def _serve() -> None:
    from mcp.server import Server  # noqa: PLC0415
    from mcp.server.stdio import stdio_server  # noqa: PLC0415
    from mcp.types import TextContent, Tool  # noqa: PLC0415

    server: Server[Any, Any] = Server("agentforge-mcp-echo")

    @server.list_tools()  # type: ignore[no-untyped-call,misc]
    async def _list_tools() -> list[Tool]:  # type: ignore[no-any-unimported]
        return [
            Tool(
                name="echo",
                description="Return the supplied text unchanged.",
                inputSchema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
            )
        ]

    @server.call_tool()  # type: ignore[no-untyped-call,misc]
    async def _call_tool(  # type: ignore[no-any-unimported]
        name: str, arguments: dict[str, Any]
    ) -> list[TextContent]:
        if name != "echo":
            msg = f"unknown tool: {name!r}"
            raise ValueError(msg)
        return [TextContent(type="text", text=str(arguments.get("text", "")))]

    options = server.create_initialization_options()
    async with stdio_server() as (read, write):
        await server.run(read, write, options)


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
