"""Unit tests for `Plan`, `PlanStep`, and `_topological_batches`."""

from __future__ import annotations

import pytest
from agentforge.strategies._plan import Plan, PlanStep, _topological_batches
from pydantic import ValidationError

# ---- PlanStep ----


def test_plan_step_basic() -> None:
    step = PlanStep(id="s1", description="do thing", tool="ping")
    assert step.id == "s1"
    assert step.tool == "ping"
    assert step.depends_on == []
    assert step.arguments == {}


def test_plan_step_is_frozen() -> None:
    step = PlanStep(id="s1", description="x")
    with pytest.raises(ValidationError):
        step.id = "s2"  # type: ignore[misc]


def test_plan_step_empty_id_rejected() -> None:
    with pytest.raises(ValidationError):
        PlanStep(id="", description="x")


def test_plan_step_tool_optional() -> None:
    step = PlanStep(id="s1", description="think")
    assert step.tool is None


# ---- Plan validation ----


def test_plan_basic() -> None:
    plan = Plan(steps=[PlanStep(id="a", description="a")])
    assert len(plan.steps) == 1


def test_plan_requires_at_least_one_step() -> None:
    with pytest.raises(ValidationError):
        Plan(steps=[])


def test_plan_rejects_duplicate_ids() -> None:
    with pytest.raises(ValidationError, match="unique"):
        Plan(
            steps=[
                PlanStep(id="a", description="x"),
                PlanStep(id="a", description="y"),
            ]
        )


def test_plan_rejects_dangling_dependency() -> None:
    with pytest.raises(ValidationError, match="not a plan step id"):
        Plan(
            steps=[
                PlanStep(id="a", description="x", depends_on=["nope"]),
            ]
        )


def test_plan_rejects_self_dependency() -> None:
    with pytest.raises(ValidationError, match="depends on itself"):
        Plan(
            steps=[
                PlanStep(id="a", description="x", depends_on=["a"]),
            ]
        )


def test_plan_rejects_cycle() -> None:
    with pytest.raises(ValidationError, match="Cycle"):
        Plan(
            steps=[
                PlanStep(id="a", description="x", depends_on=["b"]),
                PlanStep(id="b", description="y", depends_on=["a"]),
            ]
        )


def test_plan_accepts_chain() -> None:
    plan = Plan(
        steps=[
            PlanStep(id="a", description="step 1"),
            PlanStep(id="b", description="step 2", depends_on=["a"]),
            PlanStep(id="c", description="step 3", depends_on=["b"]),
        ]
    )
    assert len(plan.steps) == 3


# ---- _topological_batches ----


def test_topological_batches_independent_steps_one_batch() -> None:
    steps = [
        PlanStep(id="a", description="x"),
        PlanStep(id="b", description="y"),
        PlanStep(id="c", description="z"),
    ]
    batches = _topological_batches(steps)
    assert len(batches) == 1
    assert {s.id for s in batches[0]} == {"a", "b", "c"}


def test_topological_batches_chain_one_per_batch() -> None:
    steps = [
        PlanStep(id="a", description="x"),
        PlanStep(id="b", description="y", depends_on=["a"]),
        PlanStep(id="c", description="z", depends_on=["b"]),
    ]
    batches = _topological_batches(steps)
    assert len(batches) == 3
    assert [s.id for batch in batches for s in batch] == ["a", "b", "c"]


def test_topological_batches_diamond() -> None:
    """a → {b, c} → d   (b and c independent)"""
    steps = [
        PlanStep(id="a", description="root"),
        PlanStep(id="b", description="left", depends_on=["a"]),
        PlanStep(id="c", description="right", depends_on=["a"]),
        PlanStep(id="d", description="join", depends_on=["b", "c"]),
    ]
    batches = _topological_batches(steps)
    assert len(batches) == 3
    assert [s.id for s in batches[0]] == ["a"]
    assert {s.id for s in batches[1]} == {"b", "c"}
    assert [s.id for s in batches[2]] == ["d"]


def test_topological_batches_raises_on_cycle() -> None:
    """Cycle wouldn't pass Plan's model_validator, but the helper itself
    must also surface the error if called directly with raw steps."""
    steps = [
        PlanStep(id="a", description="x", depends_on=["b"]),
        PlanStep(id="b", description="y", depends_on=["a"]),
    ]
    with pytest.raises(ValueError, match="Cycle"):
        _topological_batches(steps)
