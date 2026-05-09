"""Unit tests for `Step`, `AgentState`, `RunResult`."""

from __future__ import annotations

import pytest
from agentforge_core.values.messages import ToolCall
from agentforge_core.values.state import AgentState, RunResult, Step
from pydantic import ValidationError

# ---- Step ----


def test_step_basic() -> None:
    s = Step(iteration=0, kind="think", content="planning")
    assert s.iteration == 0
    assert s.kind == "think"
    assert s.content == "planning"
    assert s.tool_call is None
    assert s.tokens_in == 0


def test_step_with_tool_call() -> None:
    tc = ToolCall(id="t-1", name="ping", arguments={})
    s = Step(iteration=1, kind="act", content={"x": 1}, tool_call=tc)
    assert s.tool_call is tc


def test_step_is_frozen() -> None:
    s = Step(iteration=0, kind="think", content="x")
    with pytest.raises(ValidationError):
        s.iteration = 5  # type: ignore[misc]


def test_step_rejects_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        Step(iteration=0, kind="bogus", content="x")  # type: ignore[arg-type]


def test_step_rejects_negative_iteration() -> None:
    with pytest.raises(ValidationError):
        Step(iteration=-1, kind="think", content="x")


# ---- AgentState ----


def test_agent_state_basic() -> None:
    state = AgentState(run_id="r1", task="hello")
    assert state.run_id == "r1"
    assert state.task == "hello"
    assert state.steps == []
    assert state.findings == []


def test_agent_state_appends_steps() -> None:
    state = AgentState(run_id="r1", task="t")
    s = Step(iteration=0, kind="think", content="planning")
    state.steps.append(s)
    assert len(state.steps) == 1


def test_agent_state_validate_assignment() -> None:
    """Strict mode + validate_assignment rejects bad replacements."""
    state = AgentState(run_id="r1", task="t")
    with pytest.raises(ValidationError):
        state.run_id = 42  # type: ignore[assignment]


# ---- RunResult ----


def test_run_result_basic() -> None:
    r = RunResult(
        output="hello",
        cost_usd=0.001,
        tokens_in=10,
        tokens_out=5,
        run_id="r1",
        duration_ms=120,
    )
    assert r.output == "hello"
    assert r.finish_reason == "completed"


def test_run_result_is_frozen() -> None:
    r = RunResult(
        output="x",
        cost_usd=0.0,
        tokens_in=0,
        tokens_out=0,
        run_id="r1",
        duration_ms=0,
    )
    with pytest.raises(ValidationError):
        r.output = "y"  # type: ignore[misc]


def test_run_result_rejects_negative_duration() -> None:
    with pytest.raises(ValidationError):
        RunResult(
            output="x",
            cost_usd=0.0,
            tokens_in=0,
            tokens_out=0,
            run_id="r1",
            duration_ms=-1,
        )


@pytest.mark.parametrize(
    "reason",
    ["completed", "iteration_cap", "budget_exceeded", "guardrail", "error", "cancelled"],
)
def test_run_result_accepts_every_finish_reason(reason: str) -> None:
    RunResult(
        output="x",
        cost_usd=0.0,
        tokens_in=0,
        tokens_out=0,
        run_id="r1",
        duration_ms=0,
        finish_reason=reason,  # type: ignore[arg-type]
    )
