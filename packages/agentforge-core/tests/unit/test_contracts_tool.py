"""Unit tests for the `Tool` ABC."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pytest
from agentforge_core.contracts.tool import Tool
from pydantic import BaseModel


class _PingInput(BaseModel):
    target: str


class PingTool(Tool):
    name = "ping"
    description = "Pings a target."
    input_schema = _PingInput

    async def run(self, target: str) -> dict[str, Any]:
        return {"target": target, "ok": True}


def test_tool_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError, match="abstract"):
        Tool()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_minimal_subclass_works() -> None:
    tool = PingTool()
    result = await tool.run(target="example.com")
    assert result == {"target": "example.com", "ok": True}


def test_to_spec_returns_tool_spec_with_inferred_schema() -> None:
    spec = PingTool().to_spec()
    assert spec.name == "ping"
    assert spec.description == "Pings a target."
    assert spec.schema_["type"] == "object"
    assert "target" in spec.schema_["properties"]


def test_default_capabilities_is_frozen_empty_set() -> None:
    assert PingTool.capabilities == frozenset()


def test_subclass_must_declare_required_attrs() -> None:
    with pytest.raises(TypeError, match="must declare class attribute"):

        class _Incomplete(Tool):
            async def run(self, **kwargs: Any) -> Any:
                return None


def test_intermediate_abstract_subclass_does_not_trigger_check() -> None:
    """An intermediate abstract subclass (no `name`) is allowed; only
    concrete subclasses must declare the attributes."""

    class _AbstractMixin(Tool):
        @abstractmethod
        async def run(self, **kwargs: Any) -> Any: ...

    # No error at class creation. Concrete child must still declare attrs.
    class _Concrete(_AbstractMixin):
        name = "x"
        description = "y"
        input_schema = _PingInput

        async def run(self, **kwargs: Any) -> Any:
            return None

    _Concrete()


def test_inherited_attributes_satisfy_the_check() -> None:
    """If `name` etc. come from an intermediate concrete class, fine."""

    class _Base(Tool):
        name = "base"
        description = "base desc"
        input_schema = _PingInput

        async def run(self, **kwargs: Any) -> Any:
            return None

    class _Child(_Base):
        # inherits all three attributes
        async def run(self, **kwargs: Any) -> Any:
            return "child"

    assert _Child.name == "base"
