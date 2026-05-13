"""Unit tests for `PhoenixHook` (feat-009 v0.2 follow-up)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from agentforge_core.production.run_context import bind_run, new_run, reset_run
from agentforge_core.values.messages import ToolCall
from agentforge_core.values.state import RunResult, Step
from agentforge_phoenix import PhoenixHook
from agentforge_phoenix._inmem_runner import FakePhoenixRunner


@pytest.fixture
def bound_run_id() -> Iterator[str]:
    ctx = new_run(task="t")
    token = bind_run(ctx)
    try:
        yield ctx.run_id
    finally:
        reset_run(token)


def test_step_logs_under_active_run(bound_run_id: str) -> None:
    runner = FakePhoenixRunner()
    hook = PhoenixHook(runner=runner, project_name="my-agent")

    hook(Step(iteration=0, kind="think", content="x", duration_ms=10, cost_usd=0.01))

    assert len(runner.steps) == 1
    s = runner.steps[0]
    assert s["run_id"] == bound_run_id
    assert s["kind"] == "think"
    assert s["metadata"]["duration_ms"] == 10
    assert s["metadata"]["cost_usd"] == 0.01


def test_tool_call_logs_and_redacts(bound_run_id: str) -> None:
    runner = FakePhoenixRunner()
    hook = PhoenixHook(runner=runner)
    step = Step(
        iteration=0,
        kind="act",
        content="x",
        tool_call=ToolCall(
            id="t-1",
            name="web_search",
            arguments={"q": "hi", "api_key": "shh"},
        ),
    )

    hook(step)

    tc = runner.tool_calls[0]
    assert tc["tool"] == "web_search"
    assert tc["args"]["api_key"] == "<redacted>"
    assert tc["args"]["q"] == "hi"


def test_finish_logs_run_summary() -> None:
    runner = FakePhoenixRunner()
    hook = PhoenixHook(runner=runner)
    hook(
        RunResult(
            output="ok",
            cost_usd=0.42,
            tokens_in=5,
            tokens_out=7,
            run_id="r-1",
            duration_ms=123,
            finish_reason="completed",
        )
    )

    assert len(runner.runs) == 1
    r = runner.runs[0]
    assert r["run_id"] == "r-1"
    assert r["attributes"]["finish_reason"] == "completed"
    assert r["attributes"]["cost_usd"] == 0.42
    assert r["attributes"]["n_steps"] == 0


def test_step_outside_run_context_is_a_noop() -> None:
    runner = FakePhoenixRunner()
    hook = PhoenixHook(runner=runner)
    hook(Step(iteration=0, kind="think", content="x"))
    assert runner.steps == []


def test_empty_project_name_rejected() -> None:
    with pytest.raises(ValueError, match="project_name is required"):
        PhoenixHook(runner=FakePhoenixRunner(), project_name="")


def test_close_propagates() -> None:
    runner = FakePhoenixRunner()
    hook = PhoenixHook(runner=runner)
    hook.close()
    assert runner.closed


def test_project_name_and_redact_fields_exposed() -> None:
    hook = PhoenixHook(
        runner=FakePhoenixRunner(),
        project_name="my-proj",
        redact_fields=("ssn",),
    )
    assert hook.project_name == "my-proj"
    assert hook.redact_fields == ("ssn",)
