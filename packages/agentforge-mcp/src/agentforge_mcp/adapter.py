"""`MCPToolAdapter` — bridge an MCP server's tool into the
agent's `Tool` catalogue (feat-013).

Each adapter holds a reference to an `MCPClientRunner` and a
locked `MCPToolDescriptor`. The agent treats it like any other
`Tool`: `name`, `description`, `input_schema` (Pydantic), and
an async `run(**kwargs)` that round-trips through the MCP
session.
"""

from __future__ import annotations

from typing import Any, ClassVar

from agentforge_core.contracts.tool import Tool
from pydantic import BaseModel, ConfigDict

from agentforge_mcp._runner import MCPClientRunner, MCPToolDescriptor


def build_adapter(
    runner: MCPClientRunner,
    descriptor: MCPToolDescriptor,
    *,
    server_name: str,
) -> Tool:
    """Construct an `MCPToolAdapter` subclass parameterised by
    the server's descriptor.

    Tool names are prefixed with the server name so two MCP
    servers exposing `read_file` don't collide:
    `filesystem.read_file` vs `s3.read_file`.
    """
    qualified_name = f"{server_name}.{descriptor.name}"
    schema_cls = _build_input_schema(qualified_name, descriptor.input_schema)

    class _Adapter(MCPToolAdapter):
        name: ClassVar[str] = qualified_name
        description: ClassVar[str] = descriptor.description or qualified_name
        input_schema: ClassVar[type[BaseModel]] = schema_cls

    instance = _Adapter()
    instance._runner = runner
    instance._mcp_tool_name = descriptor.name
    return instance


class MCPToolAdapter(Tool):
    """Base class for MCP-backed tools.

    Concrete subclasses are synthesised per descriptor by
    `build_adapter`. The base class declares placeholder class
    attributes so the `Tool` ABC's `__init_subclass__` validator
    is satisfied; instances carry their server's runner via the
    `_runner` attribute.
    """

    name: ClassVar[str] = "mcp"
    description: ClassVar[str] = "MCP-backed tool adapter."
    input_schema: ClassVar[type[BaseModel]] = type("_NoInput", (BaseModel,), {})

    _runner: MCPClientRunner
    _mcp_tool_name: str

    async def run(self, **kwargs: Any) -> Any:
        return await self._runner.call_tool(self._mcp_tool_name, dict(kwargs))


def _build_input_schema(qualified_name: str, schema_dict: dict[str, Any]) -> type[BaseModel]:
    """Build a Pydantic model from an MCP JSON-schema dict.

    MCP advertises `inputSchema` (JSON Schema dialect) per tool.
    We accept the spec at face value: produce a permissive
    Pydantic v2 model that lets every property through and
    validates required fields. This avoids round-tripping
    JSON-schema → Pydantic → JSON-schema with possible
    divergence; the upstream server is the source of truth.
    """
    properties = schema_dict.get("properties", {}) or {}
    required = set(schema_dict.get("required", []) or [])
    fields: dict[str, Any] = {}
    annotations: dict[str, Any] = {}
    for key in properties:
        annotations[key] = Any
        fields[key] = ... if key in required else None
    namespace: dict[str, Any] = {
        "__annotations__": annotations,
        "model_config": ConfigDict(extra="allow"),
        **fields,
    }
    cls_name = "MCPInput_" + qualified_name.replace(".", "_").replace("-", "_")
    return type(cls_name, (BaseModel,), namespace)


__all__ = ["MCPToolAdapter", "build_adapter"]
