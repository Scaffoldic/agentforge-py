"""`pii_redact_basic` — regex-based PII detection + redaction
(feat-018).

Output validator. Replaces detected PII with `<redacted:KIND>`
placeholders so downstream consumers can still parse around the
redactions.

Patterns are conservative — they catch obvious cases (RFC-822
email, US-shaped SSN / phone, common credit-card and IPv4
formats) without trying to be exhaustive. For richer coverage,
install `agentforge-guard-presidio`.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from agentforge_core.contracts.guardrails import OutputValidator
from agentforge_core.resolver import register
from agentforge_core.values.guardrails import ValidationResult

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone_us", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
    ("ipv4", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")),
)


@register("guardrails.output", "pii_redact_basic")
class PIIRedactBasic(OutputValidator):
    """Regex-based PII detector + redactor (basic tier)."""

    name: ClassVar[str] = "pii_redact_basic"
    description: ClassVar[str] = (
        "Regex-based PII detector (email / phone / SSN / credit-card / IPv4) "
        "that emits `<redacted:KIND>` placeholders in the output."
    )
    cost_estimate_ms: ClassVar[int] = 2

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del context
        violations: list[str] = []
        redacted = content
        for kind, pattern in _PATTERNS:
            if pattern.search(redacted):
                violations.append(kind)
                redacted = pattern.sub(f"<redacted:{kind}>", redacted)
        if not violations:
            return ValidationResult.ok()
        return ValidationResult(
            passed=False,
            score=0.0,
            violations=tuple(violations),
            redacted_content=redacted,
        )


__all__ = ["PIIRedactBasic"]
