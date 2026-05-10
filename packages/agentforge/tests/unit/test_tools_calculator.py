"""Unit tests for the `calculator` default tool (feat-004 chunk 2)."""

from __future__ import annotations

import pytest
from agentforge.tools import calculator


@pytest.mark.asyncio
async def test_simple_addition() -> None:
    assert await calculator.run(expression="2 + 3") == 5.0


@pytest.mark.asyncio
async def test_subtraction_negative_result() -> None:
    assert await calculator.run(expression="2 - 5") == -3.0


@pytest.mark.asyncio
async def test_multiplication() -> None:
    assert await calculator.run(expression="6 * 7") == 42.0


@pytest.mark.asyncio
async def test_division() -> None:
    assert await calculator.run(expression="10 / 4") == 2.5


@pytest.mark.asyncio
async def test_floor_division() -> None:
    assert await calculator.run(expression="10 // 3") == 3.0


@pytest.mark.asyncio
async def test_modulo() -> None:
    assert await calculator.run(expression="10 % 3") == 1.0


@pytest.mark.asyncio
async def test_exponentiation() -> None:
    assert await calculator.run(expression="2 ** 10") == 1024.0


@pytest.mark.asyncio
async def test_unary_minus() -> None:
    assert await calculator.run(expression="-5") == -5.0


@pytest.mark.asyncio
async def test_unary_plus() -> None:
    assert await calculator.run(expression="+5") == 5.0


@pytest.mark.asyncio
async def test_parentheses() -> None:
    assert await calculator.run(expression="(1 + 2) * 3") == 9.0


@pytest.mark.asyncio
async def test_floats() -> None:
    assert await calculator.run(expression="1.5 + 2.25") == 3.75


@pytest.mark.asyncio
async def test_complex_expression() -> None:
    assert await calculator.run(expression="(2 + 3) * 4 - 10 / 2") == 15.0


# ---- Rejection of non-arithmetic input ----


@pytest.mark.asyncio
async def test_rejects_variable_name() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        await calculator.run(expression="x + 1")


@pytest.mark.asyncio
async def test_rejects_function_call() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        await calculator.run(expression="abs(-5)")


@pytest.mark.asyncio
async def test_rejects_attribute_access() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        await calculator.run(expression="math.pi")


@pytest.mark.asyncio
async def test_rejects_string_literal() -> None:
    with pytest.raises(ValueError, match="not a number"):
        await calculator.run(expression="'oops'")


@pytest.mark.asyncio
async def test_rejects_boolean_literal() -> None:
    """Bools are int-subclass at the Python level — explicitly
    rejected so calculator stays numeric-only."""
    with pytest.raises(ValueError, match="not a number"):
        await calculator.run(expression="True")


@pytest.mark.asyncio
async def test_rejects_list_literal() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        await calculator.run(expression="[1, 2, 3]")


@pytest.mark.asyncio
async def test_rejects_subscript() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        await calculator.run(expression="a[0]")


@pytest.mark.asyncio
async def test_rejects_walrus_assignment() -> None:
    """Walrus is a statement-y expression that we explicitly
    don't allow — calculator is for arithmetic, not bindings."""
    with pytest.raises(ValueError, match=r"not allowed|not a number"):
        await calculator.run(expression="(a := 5)")


@pytest.mark.asyncio
async def test_syntax_error_clear_message() -> None:
    with pytest.raises(ValueError, match="cannot parse"):
        await calculator.run(expression="2 +")


@pytest.mark.asyncio
async def test_division_by_zero_raises_zerodivision() -> None:
    """ZeroDivisionError surfaces rather than being wrapped — the
    LLM dispatch layer in feat-004 chunk 4 will turn raised errors
    into observation steps."""
    with pytest.raises(ZeroDivisionError):
        await calculator.run(expression="1 / 0")


# ---- Tool surface ----


def test_tool_metadata() -> None:
    assert calculator.name == "calculator"
    assert "expression" in calculator.input_schema.model_json_schema()["properties"]
    assert calculator.capabilities == frozenset()


def test_to_spec_includes_description() -> None:
    spec = calculator.to_spec()
    assert "arithmetic" in spec.description.lower()
