"""`LLMGuardInput` — wraps llm-guard input scanners (feat-018).

Scanners are configurable via the `scanners: [...]` config list.
The shipped subset is curated: `prompt_injection`, `jailbreak`,
`ban_substrings`, `secrets`. Names map to upstream
`InputScanners`; additional names pass through.
"""

from __future__ import annotations

from typing import Any, ClassVar

from agentforge_core.contracts.guardrails import InputValidator
from agentforge_core.values.guardrails import ValidationResult

from agentforge_guard_llmguard._runner import LLMGuardRunner

_SUPPORTED_SCANNERS = frozenset(
    {
        "prompt_injection",
        "jailbreak",
        "ban_substrings",
        "secrets",
    }
)


class LLMGuardInput(InputValidator):
    """LLM Guard input-scanner adapter."""

    name: ClassVar[str] = "llmguard"
    description: ClassVar[str] = (
        "Adapter for the LLM Guard input scanners. Configurable via the "
        "`scanners: [...]` list. Each scanner produces a (valid, score) pair; "
        "this validator fails if any scanner reports invalid."
    )
    cost_estimate_ms: ClassVar[int] = 25

    def __init__(
        self,
        *,
        scanners: list[str] | None = None,
        ban_substrings: list[str] | None = None,
        runner: LLMGuardRunner | None = None,
    ) -> None:
        self._scanner_names = list(scanners or ["prompt_injection"])
        self._ban_substrings = list(ban_substrings or [])
        self._runner = runner if runner is not None else self._default_runner()

    def _default_runner(self) -> LLMGuardRunner:
        """Construct the production runner with the configured scanners.

        Imports `llm_guard` lazily — the production runner does the
        actual import + scanner instantiation. Errors surface at
        first `.scan()` call rather than at construction so tests
        that inject a fake runner don't need `llm_guard` installed.
        """
        from agentforge_guard_llmguard._runner import _RealLLMGuardRunner  # noqa: PLC0415

        return _RealLLMGuardRunner(scanners=self._build_scanner_objects())

    def _build_scanner_objects(self) -> list[Any]:
        # Real scanner construction happens lazily inside the runner;
        # the production runner's first `.scan()` resolves names →
        # scanner instances via `llm_guard.input_scanners`.
        return [
            {"name": name, "ban_substrings": self._ban_substrings} for name in self._scanner_names
        ]

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del context
        sanitized, valid, scores = await self._runner.scan(content)
        violations = tuple(name for name, ok in valid.items() if not ok)
        if not violations:
            return ValidationResult.ok()
        # LLM Guard's score is "risk score" 0..1 where 1 = high risk;
        # invert to align with `ValidationResult.score` (1 = clean).
        if scores:
            risk = max(scores.values())
            score = max(0.0, 1.0 - float(risk))
        else:
            score = 0.0
        return ValidationResult(
            passed=False,
            score=score,
            violations=violations,
            redacted_content=sanitized if sanitized != content else None,
            metadata={"scores": dict(scores)},
        )


def is_supported_scanner(name: str) -> bool:
    """Return True for the curated subset; other names still pass to
    the upstream resolver but the framework doesn't guarantee them."""
    return name in _SUPPORTED_SCANNERS


__all__ = ["LLMGuardInput", "is_supported_scanner"]
