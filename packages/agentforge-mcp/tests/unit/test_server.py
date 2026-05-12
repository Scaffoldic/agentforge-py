"""Tests for `MCPServer` (feat-013 chunk 3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from agentforge_core.contracts.tool import Tool
from agentforge_mcp import MCPServer
from pydantic import BaseModel


@dataclass
class MCPFakeServerRunner:
    """Inline fake — records registrations, simulates serve/stop."""

    registered: list[dict[str, Any]] = field(default_factory=list)
    served: bool = False
    stopped: bool = False

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Any,
    ) -> None:
        self.registered.append(
            {
                "name": name,
                "description": description,
                "schema": input_schema,
                "handler": handler,
            }
        )

    async def serve(self) -> None:
        self.served = True

    async def stop(self) -> None:
        self.stopped = True


class _Inp(BaseModel):
    text: str


class _Echo(Tool):
    name = "lookup_user"
    description = "Look up user by id."
    input_schema = _Inp

    async def run(self, **kwargs: Any) -> str:
        return f"user:{kwargs.get('text', '')}"


class _Internal(Tool):
    name = "create_ticket"
    description = "Create an internal ticket."
    input_schema = _Inp

    async def run(self, **kwargs: Any) -> str:
        del kwargs
        return "ticket:42"


class _Hidden(Tool):
    name = "private"
    description = "Should not be exposed."
    input_schema = _Inp

    async def run(self, **kwargs: Any) -> str:
        del kwargs
        return ""


def test_register_tools_publishes_each() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer(tools=[_Echo(), _Internal()], runner=runner)
    count = server.register_tools()
    assert count == 2
    names = [r["name"] for r in runner.registered]
    assert names == ["lookup_user", "create_ticket"]


def test_allowed_whitelist_restricts_exposure() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer(
        tools=[_Echo(), _Internal(), _Hidden()],
        runner=runner,
        allowed=("lookup_user", "create_ticket"),
    )
    count = server.register_tools()
    assert count == 2
    assert "private" not in {r["name"] for r in runner.registered}


@pytest.mark.asyncio
async def test_handler_round_trips_through_tool() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer(tools=[_Echo()], runner=runner)
    server.register_tools()
    [registration] = runner.registered
    handler = registration["handler"]
    out = await handler({"text": "alice"})
    assert out == "user:alice"


@pytest.mark.asyncio
async def test_serve_and_stop_delegate_to_runner() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer(tools=[_Echo()], runner=runner)
    await server.serve()
    assert runner.served
    await server.stop()
    assert runner.stopped


def test_register_tools_emits_pydantic_schema_dict() -> None:
    runner = MCPFakeServerRunner()
    server = MCPServer(tools=[_Echo()], runner=runner)
    server.register_tools()
    schema = runner.registered[0]["schema"]
    assert schema["type"] == "object"
    assert "text" in schema["properties"]
