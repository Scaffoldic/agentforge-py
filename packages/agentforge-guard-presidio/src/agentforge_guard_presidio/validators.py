"""`PresidioOutput` — Microsoft Presidio adapter (feat-018)."""

from __future__ import annotations

from typing import Any, ClassVar

from agentforge_core.contracts.guardrails import OutputValidator
from agentforge_core.values.guardrails import ValidationResult

from agentforge_guard_presidio._runner import PresidioRunner

_DEFAULT_ENTITIES: tuple[str, ...] = (
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "IP_ADDRESS",
)


class PresidioOutput(OutputValidator):
    """Detect + (optionally) redact PII in the model's output."""

    name: ClassVar[str] = "presidio"
    description: ClassVar[str] = (
        "Microsoft Presidio adapter — detects PII entities above "
        "`score_threshold` and either replaces them with `<KIND>` "
        "placeholders (`action: redact`) or reports them without "
        "modification (`action: score-only`)."
    )
    cost_estimate_ms: ClassVar[int] = 40

    def __init__(
        self,
        *,
        entities: list[str] | None = None,
        score_threshold: float = 0.5,
        action: str = "redact",
        runner: PresidioRunner | None = None,
    ) -> None:
        self._entities = list(entities or _DEFAULT_ENTITIES)
        self._threshold = float(score_threshold)
        if action not in {"redact", "score-only"}:
            msg = f"unknown action {action!r}; expected 'redact' or 'score-only'."
            raise ValueError(msg)
        self._action = action
        self._runner = runner if runner is not None else self._default_runner()

    def _default_runner(self) -> PresidioRunner:
        from agentforge_guard_presidio._runner import _RealPresidioRunner  # noqa: PLC0415

        return _RealPresidioRunner()

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del context
        findings = await self._runner.analyze(content, self._entities, self._threshold)
        if not findings:
            return ValidationResult.ok()

        violations = tuple({f.entity_type for f in findings})
        redacted: str | None = None
        if self._action == "redact":
            redacted = await self._runner.anonymize(content, findings)

        return ValidationResult(
            passed=False,
            score=max(0.0, 1.0 - max(f.score for f in findings)),
            violations=violations,
            redacted_content=redacted,
            metadata={
                "findings": [
                    {
                        "entity_type": f.entity_type,
                        "start": f.start,
                        "end": f.end,
                        "score": f.score,
                    }
                    for f in findings
                ],
            },
        )


__all__ = ["PresidioOutput"]
