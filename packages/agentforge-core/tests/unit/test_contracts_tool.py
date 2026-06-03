"""Unit tests for the `Tool` ABC."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pytest
from agentforge_core.contracts.tool import Tool, validate_tool_name
from agentforge_core.production.exceptions import ProviderError, ToolNameInvalidError
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


# ---- validate_tool_name (bug-017) ----


@pytest.mark.parametrize(
    "name",
    [
        "search",
        "kb_search",
        "fs__read_file",
        "tool-1",
        "A",
        "a" * 64,
        "Mixed_Case-123",
    ],
)
def test_validate_tool_name_accepts_portable_names(name: str) -> None:
    validate_tool_name(name)  # does not raise


@pytest.mark.parametrize(
    "name",
    [
        "kb.search",  # dot — the bug-012 / bug-017 case
        "ns:tool",  # colon
        "a b",  # space
        "tool/name",  # slash
        "café",  # non-ascii
        "",  # empty
        "a" * 65,  # too long
    ],
)
def test_validate_tool_name_rejects_illegal_names(name: str) -> None:
    with pytest.raises(ToolNameInvalidError):
        validate_tool_name(name)


def test_validate_tool_name_error_is_a_provider_error() -> None:
    """Subclasses ProviderError so existing provider-failure handlers catch it."""
    with pytest.raises(ProviderError):
        validate_tool_name("kb.search")


def test_validate_tool_name_message_includes_actionable_suggestion() -> None:
    with pytest.raises(ToolNameInvalidError, match="kb_search"):
        validate_tool_name("kb.search")
