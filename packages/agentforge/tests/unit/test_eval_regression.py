"""Unit tests for `agentforge.eval.regression` (feat-006 chunk 4)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from agentforge.eval import RegressionVsBaseline
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


def _write_baseline(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "baseline.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
    return path


# --- construction / loading ------------------------------------------


def test_missing_baseline_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        RegressionVsBaseline(baseline_path=tmp_path / "does_not_exist.jsonl")


def test_invalid_json_in_baseline_raises(tmp_path):
    path = tmp_path / "broken.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        RegressionVsBaseline(baseline_path=path)


def test_missing_keys_in_baseline_raises(tmp_path):
    path = tmp_path / "incomplete.jsonl"
    path.write_text('{"task": "x"}\n', encoding="utf-8")  # missing 'expected'
    with pytest.raises(ValueError, match="must have"):
        RegressionVsBaseline(baseline_path=path)


def test_empty_baseline_file_raises(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("\n\n  \n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        RegressionVsBaseline(baseline_path=path)


def test_unknown_mode_raises(tmp_path):
    path = _write_baseline(tmp_path, [{"task": "x", "expected": "y"}])
    with pytest.raises(ValueError, match="mode must be"):
        RegressionVsBaseline(baseline_path=path, mode="semantic")  # type: ignore[arg-type]


# --- exact mode ------------------------------------------------------


@pytest.mark.asyncio
async def test_exact_match_improved(tmp_path):
    path = _write_baseline(tmp_path, [{"task": "q1", "expected": "the answer"}])
    grader = RegressionVsBaseline(baseline_path=path)
    r = await grader.evaluate(_result("the answer"), {"task": "q1"})
    assert r.score == 1.0
    assert r.label == "improved"


@pytest.mark.asyncio
async def test_exact_mismatch_regressed(tmp_path):
    path = _write_baseline(tmp_path, [{"task": "q1", "expected": "the answer"}])
    grader = RegressionVsBaseline(baseline_path=path)
    r = await grader.evaluate(_result("different output"), {"task": "q1"})
    assert r.score == 0.0
    assert r.label == "regressed"
    assert r.raw["expected"] == "the answer"
    assert r.raw["actual"] == "different output"


@pytest.mark.asyncio
async def test_no_baseline_for_task_yields_nan_score(tmp_path):
    path = _write_baseline(tmp_path, [{"task": "q1", "expected": "x"}])
    grader = RegressionVsBaseline(baseline_path=path)
    r = await grader.evaluate(_result("anything"), {"task": "q2"})
    assert math.isnan(r.score)
    assert r.label == "no_baseline"


# --- structural mode ------------------------------------------------


@pytest.mark.asyncio
async def test_structural_full_match(tmp_path):
    path = _write_baseline(tmp_path, [{"task": "q1", "expected": {"a": 1, "b": 2}}])
    grader = RegressionVsBaseline(baseline_path=path, mode="structural")
    r = await grader.evaluate(_result({"a": 1, "b": 2}), {"task": "q1"})
    assert r.score == 1.0
    assert r.label == "improved"


@pytest.mark.asyncio
async def test_structural_partial(tmp_path):
    """2 keys match out of 3 total."""
    path = _write_baseline(tmp_path, [{"task": "q1", "expected": {"a": 1, "b": 2, "c": 3}}])
    grader = RegressionVsBaseline(baseline_path=path, mode="structural")
    r = await grader.evaluate(_result({"a": 1, "b": 2, "d": 4}), {"task": "q1"})
    # 2 matched (a, b); 'c' missing; 'd' extra. Total keys = {a,b,c,d} = 4.
    assert r.score == pytest.approx(0.5)
    assert r.label == "regressed"
    assert r.raw["missing_keys"] == ["c"]
    assert r.raw["extra_keys"] == ["d"]


@pytest.mark.asyncio
async def test_structural_mismatch_value(tmp_path):
    path = _write_baseline(tmp_path, [{"task": "q1", "expected": {"a": 1, "b": 2}}])
    grader = RegressionVsBaseline(baseline_path=path, mode="structural")
    r = await grader.evaluate(_result({"a": 1, "b": 99}), {"task": "q1"})
    assert r.score == pytest.approx(0.5)
    assert r.raw["mismatched_keys"] == ["b"]


@pytest.mark.asyncio
async def test_structural_with_non_dict_output_fails(tmp_path):
    path = _write_baseline(tmp_path, [{"task": "q1", "expected": {"a": 1}}])
    grader = RegressionVsBaseline(baseline_path=path, mode="structural")
    r = await grader.evaluate(_result("string output"), {"task": "q1"})
    assert r.score == 0.0
    assert r.label == "regressed"


# --- metadata --------------------------------------------------------


def test_metadata_declares_zero_cost(tmp_path):
    path = _write_baseline(tmp_path, [{"task": "x", "expected": "y"}])
    grader = RegressionVsBaseline(baseline_path=path)
    assert grader.cost_estimate_usd == 0.0
    assert grader.name == "regression_vs_baseline"
