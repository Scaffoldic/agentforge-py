"""`Evaluator` — the locked post-run evaluator ABC, plus `EvalResult`.

feat-001 ships only the contract and the result type. feat-006 ships
deterministic graders (coverage, consistency, regression-vs-baseline,
format-compliance) and LLM-judge graders (correctness, faithfulness,
groundedness, hallucination, relevance, helpfulness) via the
`agentforge-eval-geval` module.

Evaluators run *after* the reasoning loop completes and score the
agent's output (per `docs/features/feat-006-evaluators-and-benchmarks.md`).
This is distinct from real-time validators (feat-018) which block /
redact at the moment a violation happens.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class EvalResult(BaseModel):
    """The outcome of evaluating one finding (or output)."""

    model_config = ConfigDict(frozen=True, strict=True)

    evaluator: str
    score: float
    """Conventionally in [0, 1]; NaN allowed for "not applicable"."""

    label: str | None = None
    """Optional discrete label such as "pass" / "fail" / "warn"."""

    reasoning: str | None = None
    """LLM-judge rationale or rule-based explanation."""

    raw: dict[str, Any] = Field(default_factory=dict)
    """Driver-specific extra detail — never required, never relied on."""


class Evaluator(ABC):
    """Post-run quality scorer.

    Subclasses declare:

        name: str                   — identifier surfaced in EvalResult
        cost_estimate_usd: float    — per-evaluation cost (0 for non-LLM)
    """

    name: ClassVar[str]
    cost_estimate_usd: ClassVar[float] = 0.0

    @abstractmethod
    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        """Score `finding` against this evaluator's rubric."""
