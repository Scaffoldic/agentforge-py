"""Unit tests for `EvidentlyHook` (feat-009 v0.2 follow-up)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from agentforge_core.production.run_context import bind_run, new_run, reset_run
from agentforge_core.values.messages import ToolCall
from agentforge_core.values.state import RunResult, Step
from agentforge_evidently import EvidentlyHook
from agentforge_evidently._inmem_runner import FakeEvidentlyRunner


@pytest.fixture
def bound_run_id() -> Iterator[str]:
    ctx = new_run(task="t")
    token = bind_run(ctx)
    try:
        yield ctx.run_id
    finally:
        reset_run(token)


def test_step_appends_record(bound_run_id: str) -> None:
    runner = FakeEvidentlyRunner()
    hook = EvidentlyHook(runner=runner, project="my-agent", report_dir="/tmp/x")
    hook(
        Step(
            iteration=0,
            kind="think",
            content="x",
            duration_ms=10,
            cost_usd=0.01,
            tokens_in=5,
            tokens_out=7,
        )
    )
    assert len(runner.records) == 1
    rec = runner.records[0]
    assert rec["run_id"] == bound_run_id
    assert rec["kind"] == "think"
    assert rec["cost_usd"] == 0.01
    assert rec["tokens_in"] == 5
    assert rec["has_tool_call"] is False


def test_step_with_tool_call_flags_record(bound_run_id: str) -> None:
    runner = FakeEvidentlyRunner()
    hook = EvidentlyHook(runner=runner)
    hook(
        Step(
            iteration=0,
            kind="act",
            content="x",
            tool_call=ToolCall(id="t-1", name="search", arguments={}),
        )
    )
    assert runner.records[0]["has_tool_call"] is True


def test_finish_builds_and_writes_report(bound_run_id: str, tmp_path: Path) -> None:
    runner = FakeEvidentlyRunner()
    hook = EvidentlyHook(runner=runner, project="my-agent", report_dir=tmp_path)
    hook(Step(iteration=0, kind="think", content="a", duration_ms=5))
    hook(Step(iteration=1, kind="act", content="b", duration_ms=8))
    hook(
        RunResult(
            output="ok",
            cost_usd=0.5,
            tokens_in=10,
            tokens_out=20,
            run_id=bound_run_id,
            duration_ms=42,
            finish_reason="completed",
        )
    )

    assert len(runner.reports) == 1
    report = runner.reports[0]
    assert report["project"] == "my-agent"
    # 2 step rows + 1 run-row
    assert len(report["records"]) == 3
    assert report["records"][-1]["kind"] == "__run__"
    assert report["records"][-1]["finish_reason"] == "completed"

    # Path passed to write_report points at the configured report_dir.
    assert len(runner.writes) == 1
    path, _ = runner.writes[0]
    assert path == tmp_path / f"{bound_run_id}.json"


def test_step_outside_run_context_is_a_noop() -> None:
    runner = FakeEvidentlyRunner()
    hook = EvidentlyHook(runner=runner)
    hook(Step(iteration=0, kind="think", content="x"))
    assert runner.records == []


def test_empty_project_rejected() -> None:
    with pytest.raises(ValueError, match="project is required"):
        EvidentlyHook(runner=FakeEvidentlyRunner(), project="")


def test_finish_without_prior_steps_still_writes_report() -> None:
    runner = FakeEvidentlyRunner()
    hook = EvidentlyHook(runner=runner)
    hook(
        RunResult(
            output="ok",
            cost_usd=0.0,
            tokens_in=0,
            tokens_out=0,
            run_id="r-zero",
            duration_ms=1,
            finish_reason="completed",
        )
    )
    # No step rows; just the run row.
    assert runner.reports[0]["records"] == [
        {
            "run_id": "r-zero",
            "iteration": -1,
            "kind": "__run__",
            "cost_usd": 0.0,
            "tokens_in": 0,
            "tokens_out": 0,
            "duration_ms": 1,
            "finish_reason": "completed",
            "n_steps": 0,
        }
    ]
    assert len(runner.writes) == 1


def test_close_clears_buffers_and_propagates(bound_run_id: str) -> None:
    runner = FakeEvidentlyRunner()
    hook = EvidentlyHook(runner=runner)
    hook(Step(iteration=0, kind="think", content="x"))
    hook.close()
    assert runner.closed
