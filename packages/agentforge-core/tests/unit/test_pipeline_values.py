"""Unit tests for `PipelineResult` value model (feat-015)."""

from __future__ import annotations

import pytest
from agentforge_core.values.pipeline import PipelineResult
from pydantic import ValidationError


def test_pipeline_result_default_construction() -> None:
    r = PipelineResult()
    assert r.findings == ()
    assert r.task_durations_ms == {}
    assert r.task_failures == {}
    assert r.total_cost_usd == 0.0


def test_pipeline_result_is_frozen() -> None:
    r = PipelineResult()
    with pytest.raises(ValidationError):
        r.total_cost_usd = 1.0  # type: ignore[misc]


def test_pipeline_result_total_cost_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        PipelineResult(total_cost_usd=-0.01)


def test_pipeline_result_round_trip_json() -> None:
    r = PipelineResult(
        findings=(),
        task_durations_ms={"a": 12, "b": 3},
        task_failures={"c": "boom"},
        total_cost_usd=0.42,
    )
    blob = r.model_dump_json()
    restored = PipelineResult.model_validate_json(blob)
    assert restored == r
