"""Guardrail runtime value types (feat-018).

`ValidationResult` is the locked return shape every `InputValidator`,
`OutputValidator`, and `ToolCallGate` produces. The framework-wide
`GuardrailPolicy` lives in `agentforge_core.config.schema` instead
of here — co-locating it with the other config models avoids the
import cycle through `values.state`.

Per ADR-0009 this shape is frozen so it crosses process / module
boundaries safely.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ValidationResult(BaseModel):
    """Outcome of one validator's `validate(...)` / `authorize(...)` call."""

    model_config = ConfigDict(frozen=True, strict=True)

    passed: bool
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    """Confidence; 1.0 = definitely clean, 0.0 = definitely bad. Used
    by redaction-vs-block policy thresholds and audit aggregation."""

    violations: tuple[str, ...] = ()
    """Rule identifiers that fired (e.g. `("prompt_injection", "jailbreak")`).
    Empty tuple when `passed=True`."""

    redacted_content: str | None = None
    """If the validator can both flag AND redact, the post-redaction
    string. Output validators with `policy.on_output_violation =
    "redact"` use this; input validators usually only flag."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Validator-specific extra detail — scores per entity, spans,
    upstream raw payload. Never required, never relied on."""

    @classmethod
    def ok(cls) -> ValidationResult:
        """Clean-pass result with no violations and full confidence."""
        return cls(passed=True)


__all__ = ["ValidationResult"]
