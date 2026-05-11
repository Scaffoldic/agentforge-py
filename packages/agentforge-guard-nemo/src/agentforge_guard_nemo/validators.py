"""`NemoInput` / `NemoOutput` — NeMo Guardrails adapters (feat-018)."""

from __future__ import annotations

from typing import Any, ClassVar

from agentforge_core.contracts.guardrails import InputValidator, OutputValidator
from agentforge_core.values.guardrails import ValidationResult

from agentforge_guard_nemo._runner import NemoRunner


class _NemoMixin:
    """Shared construction surface for the input + output adapters."""

    name: ClassVar[str]
    description: ClassVar[str]
    cost_estimate_ms: ClassVar[int] = 50

    def __init__(
        self,
        *,
        config_path: str | None = None,
        runner: NemoRunner | None = None,
    ) -> None:
        if runner is None and config_path is None:
            msg = "NeMo adapter requires either `config_path` or an explicit `runner`."
            raise ValueError(msg)
        self._runner = runner if runner is not None else self._default_runner(config_path)

    def _default_runner(self, config_path: str | None) -> NemoRunner:
        from agentforge_guard_nemo._runner import _RealNemoRunner  # noqa: PLC0415

        if config_path is None:  # pragma: no cover — guarded in __init__
            msg = "config_path required"
            raise ValueError(msg)
        return _RealNemoRunner(config_path)


class NemoInput(_NemoMixin, InputValidator):
    """NeMo input rail wrapper."""

    name: ClassVar[str] = "nemo"
    description: ClassVar[str] = (
        "Run the user input through a NeMo Guardrails rail. The rail's "
        "directory (`config_path`) carries a Colang program; the validator "
        "fails when the rail elects to intervene."
    )

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del context
        result = await self._runner.check_input(content)
        if result.allowed:
            return ValidationResult.ok()
        return ValidationResult(
            passed=False,
            score=0.0,
            violations=("nemo_input_rail",),
            metadata={"rationale": result.rationale or ""},
        )


class NemoOutput(_NemoMixin, OutputValidator):
    """NeMo output rail wrapper."""

    name: ClassVar[str] = "nemo"
    description: ClassVar[str] = (
        "Run the model output through a NeMo Guardrails rail; the validator "
        "fails when the rail intervenes."
    )

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del context
        result = await self._runner.check_output(content)
        if result.allowed:
            return ValidationResult.ok()
        return ValidationResult(
            passed=False,
            score=0.0,
            violations=("nemo_output_rail",),
            metadata={"rationale": result.rationale or ""},
        )


__all__ = ["NemoInput", "NemoOutput"]
