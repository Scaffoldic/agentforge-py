"""`prompt_injection_basic` — regex pattern matching for the most
common prompt-injection phrases (feat-018).

This is the *basic* tier — it catches the obvious cases ("ignore
previous instructions") and almost nothing else. Production
deployments install `agentforge-guard-llmguard` or
`agentforge-guard-llamaguard` for richer coverage.

The pattern set is intentionally conservative: false positives are
expensive (block user) so we only flag phrases with very high
prior probability of malicious intent.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from agentforge_core.contracts.guardrails import InputValidator
from agentforge_core.resolver import register
from agentforge_core.values.guardrails import ValidationResult

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_previous",
        re.compile(
            r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions?|prompts?|messages?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "disregard_instructions",
        re.compile(r"\bdisregard\s+(?:all\s+)?(?:your\s+)?instructions?\b", re.IGNORECASE),
    ),
    (
        "system_prompt_leak",
        re.compile(
            r"\b(?:reveal|print|show|repeat|leak|dump)\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "act_as_jailbreak",
        re.compile(
            r"\bact\s+as\s+(?:dan|jailbroken|developer\s+mode|do\s+anything\s+now)\b", re.IGNORECASE
        ),
    ),
    (
        "new_persona",
        re.compile(
            r"\byou\s+are\s+now\s+(?:dan|jailbroken|in\s+developer\s+mode)\b", re.IGNORECASE
        ),
    ),
    (
        "bypass_safety",
        re.compile(
            r"\b(?:bypass|disable|turn\s+off)\s+(?:safety|guardrails?|filter|moderation)\b",
            re.IGNORECASE,
        ),
    ),
)


@register("guardrails.input", "prompt_injection_basic")
class PromptInjectionBasic(InputValidator):
    """Regex-based prompt-injection detector (basic tier)."""

    name: ClassVar[str] = "prompt_injection_basic"
    description: ClassVar[str] = (
        "Regex-based detector for the most common prompt-injection phrases. "
        "Conservative pattern set — false positives are expensive."
    )
    cost_estimate_ms: ClassVar[int] = 1

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del context
        violations: list[str] = []
        for rule, pattern in _PATTERNS:
            if pattern.search(content):
                violations.append(rule)
        if violations:
            return ValidationResult(
                passed=False,
                score=0.0,
                violations=tuple(violations),
            )
        return ValidationResult.ok()


__all__ = ["PromptInjectionBasic"]
