"""Unit tests for `agentforge.eval.consistency` (feat-006 chunk 5)."""

from __future__ import annotations

import pytest
from agentforge.eval import Consistency
from agentforge_core.values.state import RunResult


def _result(output):
    return RunResult(
        output=output,
        cost_usd=0.0,
        tokens_in=0,
        tokens_out=0,
        run_id="01TEST",
        duration_ms=0,
    )


@pytest.mark.asyncio
async def test_all_reruns_match_full_score():
    async def runner(task):
        del task
        return "stable answer"

    grader = Consistency(runner=runner, n_samples=3)
    r = await grader.evaluate(_result("stable answer"), {"task": "q"})
    assert r.score == 1.0
    assert r.label == "pass"
    assert r.raw["agreements"] == 3


@pytest.mark.asyncio
async def test_no_reruns_match_zero_score():
    counter = {"n": 0}

    async def runner(task):
        counter["n"] += 1
        return f"different-{counter['n']}"

    grader = Consistency(runner=runner, n_samples=3)
    r = await grader.evaluate(_result("the original"), {"task": "q"})
    assert r.score == 0.0
    assert r.label == "fail"


@pytest.mark.asyncio
async def test_partial_match_warn():
    """2 of 3 re-runs match → score 2/3, label warn."""
    outputs = iter(["match", "different", "match"])

    async def runner(task):
        del task
        return next(outputs)

    grader = Consistency(runner=runner, n_samples=3)
    r = await grader.evaluate(_result("match"), {"task": "q"})
    assert r.score == pytest.approx(2 / 3)
    assert r.label == "warn"


@pytest.mark.asyncio
async def test_custom_matcher_for_fuzzy_compare():
    """Case-insensitive matcher treats different cases as equal."""

    async def runner(task):
        del task
        return "STABLE ANSWER"

    def case_insensitive(a, b):
        return str(a).lower() == str(b).lower()

    grader = Consistency(runner=runner, n_samples=2, matcher=case_insensitive)
    r = await grader.evaluate(_result("stable answer"), {"task": "q"})
    assert r.score == 1.0


@pytest.mark.asyncio
async def test_runner_failure_marks_fail():
    async def runner(task):
        del task
        raise RuntimeError("LLM down")

    grader = Consistency(runner=runner, n_samples=3)
    r = await grader.evaluate(_result("original"), {"task": "q"})
    assert r.score == 0.0
    assert r.label == "fail"
    assert "RuntimeError" in (r.reasoning or "")


@pytest.mark.asyncio
async def test_missing_task_in_context_fails_cleanly():
    async def runner(task):
        del task
        return "x"

    grader = Consistency(runner=runner, n_samples=1)
    r = await grader.evaluate(_result("y"), {})  # no 'task' in context
    assert r.score == 0.0
    assert r.label == "fail"
    assert "task" in (r.reasoning or "")


@pytest.mark.asyncio
async def test_n_samples_zero_rejected():
    async def runner(task):
        del task
        return "x"

    with pytest.raises(ValueError, match="n_samples"):
        Consistency(runner=runner, n_samples=0)


@pytest.mark.asyncio
async def test_metadata_declares_zero_cost():
    async def runner(task):
        del task
        return "x"

    grader = Consistency(runner=runner, n_samples=1)
    assert grader.cost_estimate_usd == 0.0
    assert grader.name == "consistency"


@pytest.mark.asyncio
async def test_runner_called_n_times():
    calls = []

    async def runner(task):
        calls.append(task)
        return "x"

    grader = Consistency(runner=runner, n_samples=5)
    await grader.evaluate(_result("x"), {"task": "the task"})
    assert calls == ["the task"] * 5
