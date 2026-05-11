"""Tests for guardrail ABCs + values (feat-018 chunk 1)."""

from __future__ import annotations

from typing import Any

import pytest
from agentforge_core.config.schema import GuardrailPolicy
from agentforge_core.contracts.guardrails import (
    InputValidator,
    OutputValidator,
    ToolCallGate,
)
from agentforge_core.contracts.tool import Tool
from agentforge_core.values.guardrails import ValidationResult
from pydantic import BaseModel, ValidationError

# ------------------------------------------------------------------
# ValidationResult
# ------------------------------------------------------------------


def test_validation_result_ok_factory() -> None:
    result = ValidationResult.ok()
    assert result.passed is True
    assert result.score == pytest.approx(1.0)
    assert result.violations == ()
    assert result.redacted_content is None


def test_validation_result_is_frozen() -> None:
    result = ValidationResult.ok()
    with pytest.raises(ValidationError):
        result.passed = False  # type: ignore[misc]


def test_validation_result_score_must_be_in_unit_interval() -> None:
    with pytest.raises(ValidationError):
        ValidationResult(passed=False, score=1.5)


# ------------------------------------------------------------------
# GuardrailPolicy
# ------------------------------------------------------------------


def test_guardrail_policy_defaults_are_conservative() -> None:
    """Per P6 (loud defaults) — block input, redact output, block
    tool calls when a gate denies."""
    policy = GuardrailPolicy()
    assert policy.on_input_violation == "block"
    assert policy.on_output_violation == "redact"
    assert policy.on_tool_violation == "block"
    assert policy.audit_channel == "agentforge.audit"
    assert policy.fail_open is False


def test_guardrail_policy_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        GuardrailPolicy(on_input_violation="ignore")  # type: ignore[arg-type]


# ------------------------------------------------------------------
# InputValidator / OutputValidator / ToolCallGate ABCs
# ------------------------------------------------------------------


class _Inputs(BaseModel):
    text: str


class _DummyTool(Tool):
    name = "echo"
    description = "Echo input back."
    input_schema = _Inputs

    async def run(self, **kwargs: Any) -> str:
        return str(kwargs.get("text", ""))


class _AllowInput(InputValidator):
    name = "allow"
    description = "Always allows input."

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del content, context
        return ValidationResult.ok()


class _AllowOutput(OutputValidator):
    name = "allow"
    description = "Always allows output."

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del content, context
        return ValidationResult.ok()


class _AllowGate(ToolCallGate):
    name = "allow"
    description = "Always authorises tool calls."

    async def authorize(
        self,
        tool_name: str,
        tool: Tool,
        args: dict[str, Any],
        context: dict[str, Any],
    ) -> ValidationResult:
        del tool_name, tool, args, context
        return ValidationResult.ok()


@pytest.mark.asyncio
async def test_concrete_subclasses_work() -> None:
    assert (await _AllowInput().validate("x", {})).passed
    assert (await _AllowOutput().validate("x", {})).passed
    assert (await _AllowGate().authorize("t", _DummyTool(), {}, {})).passed


def test_subclass_missing_name_raises() -> None:
    with pytest.raises(TypeError, match="must declare class attribute 'name'"):

        class _Bad(InputValidator):
            description = "missing name"

            async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
                del content, context
                return ValidationResult.ok()
