"""Unit tests for the `Pipeline` engine (feat-015)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any

import pytest
from agentforge.findings import SimpleFinding
from agentforge.pipeline import Pipeline, PipelineFailure
from agentforge.resolver_register import register_task
from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.task import Task
from agentforge_core.resolver import Resolver
from agentforge_core.values.pipeline import PipelineResult


class _SimpleTask(Task):
    name = "_template_simple"

    async def run(self, context: Mapping[str, Any]) -> list[Finding]:
        return [SimpleFinding(severity="info", category=type(self).name, message="ok")]


def _make_simple(task_name: str, depends_on: tuple[str, ...] = ()) -> Task:
    cls = type(
        f"_T_{task_name}",
        (Task,),
        {
            "name": task_name,
            "depends_on": depends_on,
            "run": _SimpleTask.run,
        },
    )
    return cls()


@pytest.mark.asyncio
async def test_three_independent_tasks_run() -> None:
    pipeline = Pipeline([_make_simple("a"), _make_simple("b"), _make_simple("c")])
    result = await pipeline.run({})
    assert isinstance(result, PipelineResult)
    cats = {f.category for f in result.findings}
    assert cats == {"a", "b", "c"}
    assert result.task_failures == {}
    assert set(result.task_durations_ms) == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_dependent_sees_prior_findings_in_context() -> None:
    captured: dict[str, list[Finding]] = {}

    class _Upstream(Task):
        name = "upstream"

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            return [SimpleFinding(severity="info", category="upstream", message="hi")]

    class _Downstream(Task):
        name = "downstream"
        depends_on = ("upstream",)

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            captured["downstream"] = list(context.get("pipeline_findings_so_far", []))
            return []

    pipeline = Pipeline([_Upstream(), _Downstream()])
    await pipeline.run({"repo_path": "./repo"})
    assert any(f.category == "upstream" for f in captured["downstream"])


@pytest.mark.asyncio
async def test_max_concurrent_caps_parallelism() -> None:
    sleep_s = 0.05

    class _Sleeper(Task):
        name = "_template_sleeper"

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            await asyncio.sleep(sleep_s)
            return []

    def make(n: int) -> Task:
        return type(f"_S_{n}", (Task,), {"name": f"s{n}", "run": _Sleeper.run})()

    tasks = [make(i) for i in range(4)]

    t0 = time.monotonic()
    await Pipeline(tasks, max_concurrent=4).run({})
    parallel_elapsed = time.monotonic() - t0

    t0 = time.monotonic()
    await Pipeline([make(i + 100) for i in range(4)], max_concurrent=1).run({})
    serial_elapsed = time.monotonic() - t0

    assert parallel_elapsed < 0.15
    assert serial_elapsed > parallel_elapsed


@pytest.mark.asyncio
async def test_continue_isolates_failure_and_emits_task_failure_finding() -> None:
    class _Boom(Task):
        name = "boom"

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            raise RuntimeError("kaboom")

    pipeline = Pipeline([_Boom(), _make_simple("ok")], on_task_error="continue")
    result = await pipeline.run({})
    assert "boom" in result.task_failures
    assert "kaboom" in result.task_failures["boom"]
    cats = {f.category for f in result.findings}
    assert "pipeline.task_failure" in cats
    assert "ok" in cats


@pytest.mark.asyncio
async def test_fail_mode_raises_pipeline_failure() -> None:
    class _Boom(Task):
        name = "boom"

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            raise RuntimeError("kaboom")

    pipeline = Pipeline([_Boom(), _make_simple("ok")], on_task_error="fail")
    with pytest.raises(PipelineFailure):
        await pipeline.run({})


def test_duplicate_name_raises_at_construction() -> None:
    with pytest.raises(ValueError, match="duplicate task name"):
        Pipeline([_make_simple("a"), _make_simple("a")])


def test_missing_dep_raises_at_construction() -> None:
    with pytest.raises(ValueError, match="depends on unknown task"):
        Pipeline([_make_simple("a", depends_on=("ghost",))])


def test_cycle_raises_at_construction() -> None:
    with pytest.raises(ValueError, match="cycle in pipeline DAG"):
        Pipeline(
            [
                _make_simple("a", depends_on=("b",)),
                _make_simple("b", depends_on=("a",)),
            ]
        )


def test_invalid_max_concurrent_raises() -> None:
    with pytest.raises(ValueError, match="max_concurrent"):
        Pipeline([], max_concurrent=0)


def test_invalid_on_task_error_raises() -> None:
    with pytest.raises(ValueError, match="on_task_error"):
        Pipeline([], on_task_error="abort")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_timeout_surfaces_as_failure_finding() -> None:
    class _Slow(Task):
        name = "slow"
        timeout_s = 0.02

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            await asyncio.sleep(1.0)
            return []

    result = await Pipeline([_Slow()]).run({})
    assert "slow" in result.task_failures
    assert any(f.category == "pipeline.task_failure" for f in result.findings)


def test_pipeline_exposes_immutable_views() -> None:
    p = Pipeline([_make_simple("a")], max_concurrent=2, on_task_error="continue")
    assert isinstance(p.tasks, tuple)
    assert p.max_concurrent == 2
    assert p.on_task_error == "continue"


def test_register_task_helper_works() -> None:
    @register_task("_unit_test_task_marker")
    class _RegTask(Task):
        name = "_unit_test_task_marker"

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            return []

    # Resolver lookup verifies registration without instantiating.
    resolved = Resolver.global_().resolve("tasks", "_unit_test_task_marker")
    assert resolved is _RegTask


@pytest.mark.asyncio
async def test_cost_accumulates() -> None:
    class _Paid(Task):
        name = "paid"
        cost_estimate_usd = 0.25

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            return []

    result = await Pipeline([_Paid()]).run({})
    assert result.total_cost_usd == pytest.approx(0.25)
