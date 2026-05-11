"""Tests for `MCPServerClient` (feat-013 chunk 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from agentforge_mcp import MCPServerClient
from agentforge_mcp._runner import MCPToolDescriptor


@dataclass
class MCPFakeClientRunner:
    """Inline fake — captures calls, returns scripted tools."""

    tools: list[MCPToolDescriptor] = field(default_factory=list)
    responses: dict[str, str] = field(default_factory=dict)
    closed: bool = False
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def list_tools(self) -> list[MCPToolDescriptor]:
        return list(self.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, dict(arguments)))
        return self.responses.get(name, "")

    async def close(self) -> None:
        self.closed = True


def _tools() -> list[MCPToolDescriptor]:
    return [
        MCPToolDescriptor(
            name="read_file",
            description="Read a file.",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        ),
        MCPToolDescriptor(
            name="list_directory",
            description="List a directory.",
            input_schema={"type": "object", "properties": {}},
        ),
        MCPToolDescriptor(
            name="write_file",
            description="Write a file.",
            input_schema={"type": "object", "properties": {}},
        ),
    ]


@pytest.mark.asyncio
async def test_discover_tools_returns_all_when_no_filter() -> None:
    runner = MCPFakeClientRunner(tools=_tools())
    client = MCPServerClient(name="fs", runner=runner)
    tools = await client.discover_tools()
    assert len(tools) == 3
    names = sorted(type(t).name for t in tools)
    assert names == ["fs.list_directory", "fs.read_file", "fs.write_file"]


@pytest.mark.asyncio
async def test_tool_filter_restricts_imported_tools() -> None:
    runner = MCPFakeClientRunner(tools=_tools())
    client = MCPServerClient(name="fs", runner=runner, tool_filter=("read_file", "list_directory"))
    tools = await client.discover_tools()
    names = sorted(type(t).name for t in tools)
    assert names == ["fs.list_directory", "fs.read_file"]


@pytest.mark.asyncio
async def test_discovered_tool_round_trips_through_runner() -> None:
    runner = MCPFakeClientRunner(
        tools=_tools(),
        responses={"read_file": "<body>"},
    )
    client = MCPServerClient(name="fs", runner=runner)
    [read_file] = (t for t in await client.discover_tools() if type(t).name == "fs.read_file")
    result = await read_file.run(path="/etc/hosts")
    assert result == "<body>"
    # The runner sees the bare name, not the prefixed one.
    assert runner.calls == [("read_file", {"path": "/etc/hosts"})]


@pytest.mark.asyncio
async def test_close_propagates_to_runner() -> None:
    runner = MCPFakeClientRunner()
    client = MCPServerClient(name="fs", runner=runner)
    await client.close()
    assert runner.closed


@pytest.mark.asyncio
async def test_from_stdio_errors_when_sdk_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without `mcp` installed, the lazy import surfaces ModuleError
    with pip remediation."""
    import sys  # noqa: PLC0415

    from agentforge_core.production.exceptions import ModuleError  # noqa: PLC0415

    monkeypatch.setitem(sys.modules, "mcp", None)
    with pytest.raises(ModuleError, match="pip install mcp"):
        await MCPServerClient.from_stdio(name="x", command="echo")


@pytest.mark.asyncio
async def test_from_http_errors_when_sdk_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys  # noqa: PLC0415

    from agentforge_core.production.exceptions import ModuleError  # noqa: PLC0415

    monkeypatch.setitem(sys.modules, "mcp", None)
    with pytest.raises(ModuleError, match="pip install mcp"):
        await MCPServerClient.from_http(name="x", url="http://localhost/mcp")


@pytest.mark.asyncio
async def test_from_sse_errors_when_sdk_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys  # noqa: PLC0415

    from agentforge_core.production.exceptions import ModuleError  # noqa: PLC0415

    monkeypatch.setitem(sys.modules, "mcp", None)
    with pytest.raises(ModuleError, match="pip install mcp"):
        await MCPServerClient.from_sse(name="x", url="http://localhost/mcp")
