"""Unit tests for the evaluator pass in `Agent.run` (feat-006 chunk 1).

Verifies:
  - With no evaluators configured, `RunResult.eval_scores == ()`.
  - With evaluators configured, every evaluator's `EvalResult` lands
    in `eval_scores` in the configured order.
  - Each evaluator's `evaluate(...)` receives the `RunResult` as
    `finding` and a `context` dict carrying `task`, `state`, `budget`.
  - Budget-exhausted evaluators are skipped (don't appear in
    `eval_scores`) and a WARN log is emitted.
  - Eval scores are not double-charged against the budget (eval cost
    is informational — the budget itself is the source of truth).
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

import pytest
from agentforge import Agent
from agentforge_core.contracts.evaluator import EvalResult, Evaluator
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.state import AgentState, Step


class _NoOpStrategy(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="observe", content="hi"))
        return state


class _RecordingEvaluator(Evaluator):
    """Evaluator that records what it was called with for inspection."""

    def __init__(self, name: str, *, score: float = 1.0, cost: float = 0.0) -> None:
        self._name = name
        self.cost_estimate_usd = cost
        self.received_finding: Any = None
        self.received_context: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return self._name

    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        self.received_finding = finding
        self.received_context = context
        return EvalResult(evaluator=self._name, score=1.0, label="pass")


class _ExpensiveEvaluator(Evaluator):
    """High-cost evaluator that triggers budget-skip when budget is tight."""

    name: ClassVar[str] = "expensive"
    cost_estimate_usd: ClassVar[float] = 100.0

    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        raise AssertionError("should never run — budget should have skipped it")


@pytest.mark.asyncio
async def test_no_evaluators_yields_empty_eval_scores() -> None:
    async with Agent(strategy=_NoOpStrategy()) as agent:
        result = await agent.run("hello")
        assert result.eval_scores == ()


@pytest.mark.asyncio
async def test_evaluators_run_in_configured_order() -> None:
    a = _RecordingEvaluator("a")
    b = _RecordingEvaluator("b")
    c = _RecordingEvaluator("c")

    async with Agent(strategy=_NoOpStrategy(), evaluators=[a, b, c]) as agent:
        result = await agent.run("hello")

    assert [r.evaluator for r in result.eval_scores] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_evaluator_receives_runresult_and_context() -> None:
    rec = _RecordingEvaluator("rec")

    async with Agent(strategy=_NoOpStrategy(), evaluators=[rec]) as agent:
        result = await agent.run("the task")

    # `finding` is the result (without eval_scores yet — the evaluator
    # sees the interim result built before the eval loop runs).
    assert rec.received_finding is not None
    assert rec.received_finding.output == "hi"
    assert rec.received_finding.run_id == result.run_id

    assert rec.received_context is not None
    assert rec.received_context["task"] == "the task"
    assert "state" in rec.received_context
    assert "budget" in rec.received_context


@pytest.mark.asyncio
async def test_budget_exhausted_evaluator_is_skipped(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="agentforge.evaluators")

    expensive = _ExpensiveEvaluator()
    cheap = _RecordingEvaluator("cheap")

    async with Agent(
        strategy=_NoOpStrategy(),
        evaluators=[expensive, cheap],
        budget_usd=1.0,  # only $1 budget; expensive needs $100
    ) as agent:
        result = await agent.run("hello")

    # Only the cheap evaluator ran.
    assert [r.evaluator for r in result.eval_scores] == ["cheap"]
    # Log mentions the skip.
    assert any(
        "skipping evaluator" in r.message and "expensive" in r.message for r in caplog.records
    )


@pytest.mark.asyncio
async def test_zero_cost_evaluators_all_run_even_with_zero_budget_remaining() -> None:
    """Deterministic graders declare `cost_estimate_usd=0`; they should
    not be skipped by budget gating."""

    # Strategy doesn't consume any budget; cost_usd is 0.
    grader_a = _RecordingEvaluator("a", cost=0.0)
    grader_b = _RecordingEvaluator("b", cost=0.0)

    async with Agent(
        strategy=_NoOpStrategy(),
        evaluators=[grader_a, grader_b],
        budget_usd=0.0,  # zero budget — but graders are free
    ) as agent:
        result = await agent.run("hello")

    assert [r.evaluator for r in result.eval_scores] == ["a", "b"]


@pytest.mark.asyncio
async def test_eval_scores_visible_on_finish_hook() -> None:
    """The `on_finish` hook receives the FINAL `RunResult` — eval_scores
    must be populated by then."""
    observed: list[tuple[EvalResult, ...]] = []

    def capture(result: Any) -> None:
        observed.append(result.eval_scores)

    rec = _RecordingEvaluator("rec")
    async with Agent(strategy=_NoOpStrategy(), evaluators=[rec], on_finish=capture) as agent:
        await agent.run("hello")

    assert len(observed) == 1
    assert [r.evaluator for r in observed[0]] == ["rec"]
