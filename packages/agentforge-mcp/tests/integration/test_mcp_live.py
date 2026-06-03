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

import sys
from pathlib import Path

import pytest
from agentforge_mcp import MCPServerClient


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
