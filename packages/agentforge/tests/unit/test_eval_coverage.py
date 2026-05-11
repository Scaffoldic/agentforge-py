"""Unit tests for `agentforge.eval.coverage` (feat-006 chunk 2)."""

from __future__ import annotations

import pytest
from agentforge.eval import Coverage
from agentforge_core.values.state import RunResult


def _result(output: str) -> RunResult:
    return RunResult(
        output=output,
        cost_usd=0.0,
        tokens_in=0,
        tokens_out=0,
        run_id="01TEST",
        duration_ms=0,
    )


@pytest.mark.asyncio
async def test_all_items_present_scores_1():
    grader = Coverage(reference={"alpha", "beta", "gamma"})
    out = _result("notes about alpha, beta, and gamma")
    r = await grader.evaluate(out, {})
    assert r.score == pytest.approx(1.0)
    assert r.label == "pass"
    assert r.raw["missing"] == []


@pytest.mark.asyncio
async def test_partial_match_scores_fraction():
    grader = Coverage(reference={"alpha", "beta", "gamma", "delta"})
    out = _result("we found alpha and gamma")
    r = await grader.evaluate(out, {})
    assert r.score == pytest.approx(0.5)
    assert r.label == "warn"
    assert sorted(r.raw["matched"]) == ["alpha", "gamma"]
    assert sorted(r.raw["missing"]) == ["beta", "delta"]


@pytest.mark.asyncio
async def test_no_items_present_scores_0_and_fails():
    grader = Coverage(reference={"alpha", "beta"})
    out = _result("totally unrelated text")
    r = await grader.evaluate(out, {})
    assert r.score == pytest.approx(0.0)
    assert r.label == "fail"


@pytest.mark.asyncio
async def test_case_insensitive_match():
    grader = Coverage(reference={"SQL Injection", "XSS"})
    out = _result("watch out for sql injection and xss attacks")
    r = await grader.evaluate(out, {})
    assert r.score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_custom_extractor_for_structured_output():
    grader = Coverage(
        reference={"item-1", "item-2", "item-3"},
        extractor=lambda out: set(out["found"]),
    )
    structured = {"found": ["item-1", "item-3"]}
    out = RunResult(
        output=structured,
        cost_usd=0.0,
        tokens_in=0,
        tokens_out=0,
        run_id="01TEST",
        duration_ms=0,
    )
    r = await grader.evaluate(out, {})
    assert r.score == pytest.approx(2 / 3)


@pytest.mark.asyncio
async def test_empty_reference_set_rejected_at_construction():
    with pytest.raises(ValueError, match="non-empty reference"):
        Coverage(reference=set())


@pytest.mark.asyncio
async def test_metadata_declares_zero_cost():
    grader = Coverage(reference={"x"})
    assert grader.cost_estimate_usd == 0.0
    assert grader.name == "coverage"
