"""Unit tests for the `@tool` decorator (feat-004 chunk 1)."""

from __future__ import annotations

import pytest
from agentforge import tool
from agentforge_core.contracts.tool import Tool
from pydantic import BaseModel, ValidationError

# ---- Bare-decorator form (no parens) ----


def test_decorator_returns_tool_instance() -> None:
    @tool
    def my_func(x: int) -> int:
        """Square x.

        Args:
            x: The number to square.
        """
        return x * x

    assert isinstance(my_func, Tool)


def test_decorator_infers_name_from_function_name() -> None:
    @tool
    def lookup_user(user_id: str) -> str:
        """Lookup."""
        return user_id

    assert lookup_user.name == "lookup_user"


def test_decorator_infers_description_from_docstring_summary() -> None:
    @tool
    def my_func(x: int) -> int:
        """One-line summary.

        Args:
            x: The input.
        """
        return x

    assert my_func.description == "One-line summary."


def test_decorator_uses_function_name_when_no_docstring() -> None:
    @tool
    def my_func(x: int) -> int:
        return x

    assert my_func.description == "my_func"


def test_decorator_handles_multiline_summary() -> None:
    @tool
    def my_func(x: int) -> int:
        """Summary line one.
        Summary line two.

        Args:
            x: The input.
        """
        return x

    # Multi-line summary collapses to single line.
    assert "one." in my_func.description.lower()
    assert "two." in my_func.description.lower()


# ---- Schema inference ----


def test_required_param_no_default_is_required_in_schema() -> None:
    @tool
    def my_func(x: int) -> int:
        """Doc.

        Args:
            x: required.
        """
        return x

    json_schema = my_func.input_schema.model_json_schema()
    assert "x" in json_schema["required"]


def test_param_with_default_is_optional_in_schema() -> None:
    @tool
    def my_func(x: int = 10) -> int:
        """Doc.

        Args:
            x: optional.
        """
        return x

    json_schema = my_func.input_schema.model_json_schema()
    assert "x" not in json_schema.get("required", [])


def test_basic_types_resolve_to_pydantic_fields() -> None:
    @tool
    def my_func(s: str, n: int, f: float, b: bool) -> str:
        """Doc."""
        return s

    json_schema = my_func.input_schema.model_json_schema()
    props = json_schema["properties"]
    assert props["s"]["type"] == "string"
    assert props["n"]["type"] == "integer"
    assert props["f"]["type"] == "number"
    assert props["b"]["type"] == "boolean"


def test_complex_types_list_dict() -> None:
    @tool
    def my_func(items: list[str], meta: dict[str, int]) -> int:
        """Doc."""
        return len(items)

    json_schema = my_func.input_schema.model_json_schema()
    assert json_schema["properties"]["items"]["type"] == "array"
    assert json_schema["properties"]["meta"]["type"] == "object"


def test_optional_type_with_none_default() -> None:
    @tool
    def my_func(name: str | None = None) -> str:
        """Doc."""
        return name or "default"

    # The model accepts None and missing; "name" should not be required.
    json_schema = my_func.input_schema.model_json_schema()
    assert "name" not in json_schema.get("required", [])


class _Address(BaseModel):
    """Module-level Pydantic model — `get_type_hints` can't resolve
    types defined inside a test function's local scope."""

    street: str
    city: str


def test_nested_pydantic_model_in_signature() -> None:
    @tool
    def update_addr(user_id: str, addr: _Address) -> bool:
        """Update an address."""
        return True

    json_schema = update_addr.input_schema.model_json_schema()
    # The Address model should appear in $defs or as inline ref.
    assert "addr" in json_schema["properties"]


def test_arg_descriptions_from_docstring_propagate_to_schema() -> None:
    @tool
    def my_func(user_id: str, include_email: bool = False) -> dict:
        """Fetch a user record.

        Args:
            user_id: The internal user id (ULID).
            include_email: When True, include the email field.
        """
        return {}

    json_schema = my_func.input_schema.model_json_schema()
    assert json_schema["properties"]["user_id"]["description"] == ("The internal user id (ULID).")
    assert json_schema["properties"]["include_email"]["description"] == (
        "When True, include the email field."
    )


# ---- Decoration-time errors ----


def test_missing_type_hint_raises() -> None:
    with pytest.raises(ValueError, match="missing a type hint"):

        @tool
        def my_func(x) -> int:  # type: ignore[no-untyped-def]
            return x


def test_var_positional_rejected() -> None:
    with pytest.raises(ValueError, match="variadic"):

        @tool
        def my_func(*args: int) -> int:
            return sum(args)


def test_var_keyword_rejected() -> None:
    with pytest.raises(ValueError, match="variadic"):

        @tool
        def my_func(**kwargs: int) -> int:
            return sum(kwargs.values())


# ---- Parameterised form (`@tool(name=..., capabilities=...)`) ----


def test_parameterised_decorator_overrides_name() -> None:
    @tool(name="custom_tool")
    def my_func(x: int) -> int:
        """Doc."""
        return x

    assert my_func.name == "custom_tool"


def test_parameterised_decorator_overrides_description() -> None:
    @tool(description="Custom override.")
    def my_func(x: int) -> int:
        """Doc."""
        return x

    assert my_func.description == "Custom override."


def test_parameterised_decorator_sets_capabilities() -> None:
    @tool(capabilities={"network", "filesystem"})
    def my_func(url: str) -> str:
        """Doc."""
        return url

    assert my_func.capabilities == frozenset({"network", "filesystem"})


def test_default_capabilities_empty() -> None:
    @tool
    def my_func(x: int) -> int:
        """Doc."""
        return x

    assert my_func.capabilities == frozenset()


# ---- run() dispatch ----


@pytest.mark.asyncio
async def test_run_dispatches_to_sync_function() -> None:
    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    result = await add.run(a=2, b=3)
    assert result == 5


@pytest.mark.asyncio
async def test_run_dispatches_to_async_function() -> None:
    @tool
    async def aadd(a: int, b: int) -> int:
        """Add asynchronously."""
        return a + b

    result = await aadd.run(a=2, b=3)
    assert result == 5


# ---- Validation via input_schema ----


def test_input_schema_validates_correct_input() -> None:
    @tool
    def my_func(x: int) -> int:
        """Doc."""
        return x

    validated = my_func.input_schema.model_validate({"x": 42})
    assert validated.x == 42  # type: ignore[attr-defined]


def test_input_schema_rejects_wrong_type() -> None:
    @tool
    def my_func(x: int) -> int:
        """Doc."""
        return x

    with pytest.raises(ValidationError):
        my_func.input_schema.model_validate({"x": "not an int"})


def test_input_schema_rejects_missing_required() -> None:
    @tool
    def my_func(x: int, y: int) -> int:
        """Doc."""
        return x + y

    with pytest.raises(ValidationError):
        my_func.input_schema.model_validate({"x": 1})


# ---- to_spec() (provider-agnostic JSON schema description) ----


def test_to_spec_returns_tool_spec_with_schema() -> None:
    @tool
    def my_func(x: int) -> int:
        """Doc summary."""
        return x

    spec = my_func.to_spec()
    assert spec.name == "my_func"
    assert spec.description == "Doc summary."
    # `ToolSpec.schema_` (aliased to `schema` in serialization).
    assert "x" in spec.schema_["properties"]
