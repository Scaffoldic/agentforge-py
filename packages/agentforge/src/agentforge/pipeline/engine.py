"""`Pipeline` — deterministic-task DAG engine (feat-015).

Runs a set of `Task` instances as a DAG (resolved via
``Task.depends_on``), respecting a ``max_concurrent`` semaphore. Each
task's execution is bounded by ``Task.timeout_s``. Failures are
handled per ``on_task_error``:

  - ``"continue"`` (default): the failed task emits a
    ``SimpleFinding`` with category ``"pipeline.task_failure"``;
    dependents still run (they see the failure-finding in their
    merged context under ``"pipeline_findings_so_far"``).
  - ``"fail"``: the engine cancels outstanding tasks and raises
    `PipelineFailure`. Findings collected before the failure are
    lost — the caller treats the run as aborted.

The output is a frozen `PipelineResult` with consolidated findings,
per-task durations, the failures map, and total cost.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any, Literal

from agentforge_core.contracts.task import Task
from agentforge_core.values.pipeline import PipelineResult

from agentforge.findings import SimpleFinding
from agentforge.pipeline.errors import PipelineFailure

OnTaskError = Literal["continue", "fail"]


class Pipeline:
    """A DAG of deterministic (or LLM-using) tasks.

    Construct once, ``run(context)`` once per agent invocation.
    Validation (duplicate names, missing deps, cycles) runs at
    construction so misconfigurations fail before the first run.
    """

    def __init__(
        self,
        tasks: list[Task],
        *,
        max_concurrent: int = 4,
        on_task_error: OnTaskError = "continue",
    ) -> None:
        if max_concurrent < 1:
            raise ValueError(f"max_concurrent must be >= 1, got {max_concurrent}")
        if on_task_error not in ("continue", "fail"):
            raise ValueError(f"on_task_error must be 'continue' or 'fail', got {on_task_error!r}")
        self._tasks = list(tasks)
        self._max_concurrent = max_concurrent
        self._on_task_error = on_task_error
        self._by_name: dict[str, Task] = {}
        for t in self._tasks:
            tname = type(t).name
            if tname in self._by_name:
                raise ValueError(f"duplicate task name in pipeline: {tname!r}")
            self._by_name[tname] = t
        self._validate_dag()

    @property
    def tasks(self) -> tuple[Task, ...]:
        return tuple(self._tasks)

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    @property
    def on_task_error(self) -> OnTaskError:
        return self._on_task_error

    def _validate_dag(self) -> None:
        for t in self._tasks:
            for dep in type(t).depends_on:
                if dep not in self._by_name:
                    raise ValueError(f"task {type(t).name!r} depends on unknown task {dep!r}")
        # cycle detection via DFS
        WHITE, GREY, BLACK = 0, 1, 2  # noqa: N806
        color = dict.fromkeys(self._by_name, WHITE)

        def visit(name: str, stack: list[str]) -> None:
            if color[name] == GREY:
                cycle = " -> ".join([*stack, name])
                raise ValueError(f"cycle in pipeline DAG: {cycle}")
            if color[name] == BLACK:
                return
            color[name] = GREY
            for dep in type(self._by_name[name]).depends_on:
                visit(dep, [*stack, name])
            color[name] = BLACK

        for name in self._by_name:
            visit(name, [])

    async def run(self, context: Mapping[str, Any]) -> PipelineResult:
        """Execute the pipeline once and return consolidated output."""
        loop = asyncio.get_running_loop()
        state = _RunState(
            semaphore=asyncio.Semaphore(self._max_concurrent),
            # Each task gets a future of its emitted findings (or [] on
            # failure when on_task_error="continue"); dependents await.
            futures={name: loop.create_future() for name in self._by_name},
        )
        runners = [asyncio.create_task(self._run_one(t, context, state)) for t in self._tasks]
        try:
            await asyncio.gather(*runners)
        except PipelineFailure:
            for r in runners:
                if not r.done():
                    r.cancel()
            await asyncio.gather(*runners, return_exceptions=True)
            raise

        return PipelineResult(
            findings=tuple(state.accumulated),
            task_durations_ms=state.durations,
            task_failures=state.failures,
            total_cost_usd=state.total_cost,
        )

    async def _run_one(self, task: Task, context: Mapping[str, Any], state: _RunState) -> None:
        tname = type(task).name
        dep_results = [await state.futures[dep] for dep in type(task).depends_on]
        prior: list[Any] = []
        for batch in dep_results:
            prior.extend(batch)
        async with state.lock:
            snapshot = list(state.accumulated)
        merged: dict[str, Any] = dict(context)
        existing = merged.get("pipeline_findings_so_far", [])
        merged["pipeline_findings_so_far"] = [*existing, *prior, *snapshot]

        start = time.monotonic()
        async with state.semaphore:
            try:
                timeout = float(type(task).timeout_s)
                findings = await asyncio.wait_for(task.run(merged), timeout=timeout)
            except Exception as exc:
                await self._record_failure(tname, exc, start, state)
                return
            elapsed = int((time.monotonic() - start) * 1000)
            state.durations[tname] = elapsed
            state.total_cost += float(type(task).cost_estimate_usd)
            async with state.lock:
                state.accumulated.extend(findings)
            state.futures[tname].set_result(list(findings))

    async def _record_failure(
        self, tname: str, exc: BaseException, start: float, state: _RunState
    ) -> None:
        elapsed = int((time.monotonic() - start) * 1000)
        state.durations[tname] = elapsed
        state.failures[tname] = str(exc) if str(exc) else repr(exc)
        if self._on_task_error == "fail":
            state.futures[tname].set_exception(PipelineFailure(tname, exc))
            raise PipelineFailure(tname, exc) from exc
        failure_finding = SimpleFinding(
            severity="error",
            category="pipeline.task_failure",
            message=f"task {tname!r} failed: {state.failures[tname]}",
            rule_id=tname,
        )
        async with state.lock:
            state.accumulated.append(failure_finding)
        state.futures[tname].set_result([failure_finding])


class _RunState:
    """Mutable per-run scratch shared across `_run_one` invocations."""

    def __init__(
        self,
        *,
        semaphore: asyncio.Semaphore,
        futures: dict[str, asyncio.Future[list[Any]]],
    ) -> None:
        self.semaphore = semaphore
        self.futures = futures
        self.accumulated: list[Any] = []
        self.durations: dict[str, int] = {}
        self.failures: dict[str, str] = {}
        self.total_cost = 0.0
        self.lock = asyncio.Lock()
