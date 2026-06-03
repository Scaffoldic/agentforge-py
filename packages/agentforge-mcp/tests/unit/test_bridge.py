"""Tests for `MCPBridge` (feat-013 chunk 4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from agentforge_core.contracts.tool import Tool
from agentforge_mcp import MCPBridge, MCPServer, MCPServerClient
from agentforge_mcp._runner import MCPToolDescriptor
from pydantic import BaseModel


@dataclass
class MCPFakeClientRunner:
    tools: list[MCPToolDescriptor] = field(default_factory=list)
    responses: dict[str, str] = field(default_factory=dict)
    closed: bool = False

    async def list_tools(self) -> list[MCPToolDescriptor]:
        return list(self.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        del name, arguments
        return self.responses.get("default", "")

    async def close(self) -> None:
        self.closed = True


@dataclass
class MCPFakeServerRunner:
    registered: list[dict[str, Any]] = field(default_factory=list)
    served: bool = False
    stopped: bool = False
    serve_event: Any = None

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Any,
    ) -> None:
        self.registered.append({"name": name})
        del description, input_schema, handler

    async def serve(self) -> None:
        import asyncio  # noqa: PLC0415

        self.served = True
        # Block until cancelled so `bridge.close` can verify the
        # serve task is cancelled cleanly.
        await asyncio.Event().wait()

    async def stop(self) -> None:
        self.stopped = True


class _Inp(BaseModel):
    text: str


class _Echo(Tool):
    name = "echo"
    description = "Echo."
    input_schema = _Inp

    async def run(self, **kwargs: Any) -> str:
        return str(kwargs.get("text", ""))


def _client(name: str, tool_names: tuple[str, ...]) -> MCPServerClient:
    descriptors = [
        MCPToolDescriptor(name=n, description=f"{n}.", input_schema={"type": "object"})
        for n in tool_names
    ]
    return MCPServerClient(
        name=name,
        runner=MCPFakeClientRunner(tools=descriptors),
    )


@pytest.mark.asyncio
async def test_bridge_aggregates_tools_from_every_client() -> None:
    bridge = MCPBridge(
        clients=[
            _client("fs", ("read_file", "write_file")),
            _client("github", ("create_issue",)),
        ]
    )
    await bridge.start()
    names = sorted(type(t).name for t in bridge.tools)
    assert names == ["fs__read_file", "fs__write_file", "github__create_issue"]


@pytest.mark.asyncio
async def test_bridge_close_propagates_to_every_client() -> None:
    runner_a = MCPFakeClientRunner()
    runner_b = MCPFakeClientRunner()
    bridge = MCPBridge(
        clients=[
            MCPServerClient(name="a", runner=runner_a),
            MCPServerClient(name="b", runner=runner_b),
        ]
    )
    await bridge.start()
    await bridge.close()
    assert runner_a.closed
    assert runner_b.closed


@pytest.mark.asyncio
async def test_bridge_starts_optional_exposed_server() -> None:
    server_runner = MCPFakeServerRunner()
    server = MCPServer(tools=[_Echo()], runner=server_runner, allowed=("echo",))
    bridge = MCPBridge(clients=[], server=server)
    await bridge.start()
    # Give the event loop a tick so the serve task fires.
    import asyncio  # noqa: PLC0415

    await asyncio.sleep(0)
    assert server_runner.served
    assert {r["name"] for r in server_runner.registered} == {"echo"}
    await bridge.close()
    assert server_runner.stopped


def test_bridge_from_config_with_no_servers_returns_empty_bridge() -> None:
    bridge = MCPBridge.from_config({})
    assert bridge.tools == []


@pytest.mark.asyncio
async def test_from_config_is_safe_inside_running_loop() -> None:
    """bug-014 regression: `from_config` must not drive the event loop.

    This test body runs inside a live asyncio loop; the pre-fix
    implementation called `get_event_loop().run_until_complete` here
    and raised `RuntimeError: this event loop is already running`.
    """
    bridge = MCPBridge.from_config(
        {"servers": [{"name": "x", "transport": "stdio", "command": "cat"}]}
    )
    # Deferred — nothing is opened until `start()`.
    assert bridge.tools == []


@pytest.mark.asyncio
async def test_start_materialises_deferred_client_specs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`from_config` stashes specs; `start()` turns them into live
    clients (here via a monkeypatched factory) and discovers tools."""
    import agentforge_mcp.bridge as bridge_mod  # noqa: PLC0415

    fake = _client("fs", ("read_file",))

    async def _fake_from_entry(entry: dict[str, Any]) -> MCPServerClient:
        assert entry["name"] == "fs"
        return fake

    monkeypatch.setattr(bridge_mod, "_client_from_entry_async", _fake_from_entry)

    bridge = MCPBridge.from_config(
        {"servers": [{"name": "fs", "transport": "stdio", "command": ["cat"]}]}
    )
    assert bridge.tools == []
    await bridge.start()
    assert sorted(type(t).name for t in bridge.tools) == ["fs__read_file"]


@pytest.mark.asyncio
async def test_attach_local_tools_exposes_them_on_serve() -> None:
    """`attach_local_tools` injects the agent's tools into the exposed
    server after construction (the loose end called out in bug-020)."""
    server_runner = MCPFakeServerRunner()
    server = MCPServer(tools=[], runner=server_runner, allowed=())
    bridge = MCPBridge(server=server)
    bridge.attach_local_tools([_Echo()])
    await bridge.start()
    import asyncio  # noqa: PLC0415

    await asyncio.sleep(0)
    assert {r["name"] for r in server_runner.registered} == {"echo"}
    await bridge.close()


def test_attach_local_tools_is_noop_without_server() -> None:
    bridge = MCPBridge(clients=[])
    # No exposed server configured — must not raise.
    bridge.attach_local_tools([_Echo()])


def test_command_str_joins_list_form() -> None:
    from agentforge_mcp.bridge import _command_str  # noqa: PLC0415

    assert _command_str(["uv", "run", "filesystem-mcp"]) == "uv run filesystem-mcp"
    assert _command_str("uv run filesystem-mcp") == "uv run filesystem-mcp"
