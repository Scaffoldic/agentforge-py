"""Tests for `MCPToolAdapter` (feat-013 chunk 1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from agentforge_mcp._runner import MCPToolDescriptor
from agentforge_mcp.adapter import build_adapter


@dataclass
class MCPFakeClientRunner:
    """Inline fake runner — captures calls, returns scripted output."""

    responses: dict[str, str] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    closed: bool = False

    async def list_tools(self) -> list[MCPToolDescriptor]:
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, dict(arguments)))
        return self.responses.get(name, "")

    async def close(self) -> None:
        self.closed = True


def _descriptor(name: str = "read_file") -> MCPToolDescriptor:
    return MCPToolDescriptor(
        name=name,
        description=f"Reads a file via {name}.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    )


def test_adapter_qualifies_name_with_server_prefix() -> None:
    runner = MCPFakeClientRunner()
    adapter = build_adapter(runner, _descriptor(), server_name="fs")
    assert type(adapter).name == "fs.read_file"
    assert "Reads a file" in type(adapter).description


def test_adapter_has_pydantic_input_schema() -> None:
    runner = MCPFakeClientRunner()
    adapter = build_adapter(runner, _descriptor(), server_name="fs")
    schema = type(adapter).input_schema
    assert "path" in schema.model_fields


@pytest.mark.asyncio
async def test_adapter_run_round_trips_through_runner() -> None:
    runner = MCPFakeClientRunner(responses={"read_file": "<file body>"})
    adapter = build_adapter(runner, _descriptor(), server_name="fs")
    out = await adapter.run(path="/etc/hosts")
    assert out == "<file body>"
    assert runner.calls == [("read_file", {"path": "/etc/hosts"})]


@pytest.mark.asyncio
async def test_adapter_strips_server_prefix_when_calling_mcp() -> None:
    """The runner should receive the bare MCP-side name
    (`read_file`), not the qualified `fs.read_file`."""
    runner = MCPFakeClientRunner(responses={"read_file": "ok"})
    adapter = build_adapter(runner, _descriptor(), server_name="fs")
    await adapter.run(path="/tmp")
    assert runner.calls[0][0] == "read_file"


def test_adapter_input_schema_missing_required_field() -> None:
    """Without `path`, validation fails; this is the contract
    agent dispatch will rely on (rejects bad LLM calls)."""
    runner = MCPFakeClientRunner()
    adapter = build_adapter(runner, _descriptor(), server_name="fs")
    schema = type(adapter).input_schema
    from pydantic import ValidationError  # noqa: PLC0415

    with pytest.raises(ValidationError):
        schema(**{})
