"""Unit tests for the `Evaluator` ABC and `EvalResult` value type."""

from __future__ import annotations

import math
from typing import Any

import pytest
from agentforge_core.contracts.evaluator import EvalResult, Evaluator
from pydantic import ValidationError

# ---- EvalResult ----


def test_eval_result_basic() -> None:
    r = EvalResult(evaluator="faithfulness", score=0.91, label="pass")
    assert r.evaluator == "faithfulness"
    assert r.score == pytest.approx(0.91)
    assert r.label == "pass"


def test_eval_result_is_frozen() -> None:
    r = EvalResult(evaluator="x", score=0.5)
    with pytest.raises(ValidationError):
        r.score = 0.6  # type: ignore[misc]


def test_eval_result_allows_nan_score() -> None:
    """Per feat-006, NaN score means 'not applicable'."""
    r = EvalResult(evaluator="coverage", score=float("nan"))
    assert math.isnan(r.score)


def test_eval_result_optional_fields_default_none() -> None:
    r = EvalResult(evaluator="x", score=0.0)
    assert r.label is None
    assert r.reasoning is None
    assert r.raw == {}


# ---- Evaluator ABC ----


def test_evaluator_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError, match="abstract"):
        Evaluator()  # type: ignore[abstract]


class FaithfulnessEvaluator(Evaluator):
    name = "faithfulness"
    cost_estimate_usd = 0.0

    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        return EvalResult(evaluator=self.name, score=0.91, label="pass")


@pytest.mark.asyncio
async def test_minimal_subclass_works() -> None:
    ev = FaithfulnessEvaluator()
    result = await ev.evaluate("anything", {})
    assert result.evaluator == "faithfulness"
    assert result.label == "pass"


def test_default_cost_estimate_zero() -> None:
    assert FaithfulnessEvaluator.cost_estimate_usd == 0.0


class _LLMJudge(Evaluator):
    name = "llm-judge"
    cost_estimate_usd = 0.05

    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        return EvalResult(evaluator=self.name, score=0.7)


def test_subclass_can_declare_cost_estimate() -> None:
    assert _LLMJudge.cost_estimate_usd == pytest.approx(0.05)
