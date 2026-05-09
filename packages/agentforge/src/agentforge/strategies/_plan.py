"""`Plan` + `PlanStep` value types and topological-sort helper.

Used by `PlanExecuteLoop` (feat-002 chunk 3). The plan is a typed
Pydantic model so the LLM's JSON output is validated at parse time;
cycle and dangling-dependency detection are enforced by a
`model_validator` and `_topological_batches`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlanStep(BaseModel):
    """One step in a `Plan`.

    Attributes:
        id: Stable identifier; `depends_on` references this.
        description: Natural-language description of what the step does.
        tool: Name of a registered tool to invoke. `None` means a
            "think" step — an LLM call reasoning about `description`
            in the context of prior step outputs.
        arguments: Keyword arguments passed to the tool's `run()`. Only
            used when `tool` is not `None`.
        depends_on: List of `PlanStep.id`s that must complete before
            this step executes. Empty list = step is independent.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    id: str = Field(min_length=1)
    description: str
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    """A topologically valid execution plan."""

    model_config = ConfigDict(frozen=True, strict=True)

    steps: list[PlanStep] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate(self) -> Plan:
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Plan step ids must be unique")
        id_set = set(ids)
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in id_set:
                    raise ValueError(
                        f"step {step.id!r} depends_on={dep!r} which is not a plan step id"
                    )
            if step.id in step.depends_on:
                raise ValueError(f"step {step.id!r} depends on itself")
        # Cycle detection — _topological_batches raises if a cycle exists.
        _topological_batches(self.steps)
        return self


def _topological_batches(steps: list[PlanStep]) -> list[list[PlanStep]]:
    """Group `steps` into a list of batches.

    Each batch contains steps whose `depends_on` set is fully covered
    by completed (earlier-batch) steps. Steps within a batch have no
    dependencies on each other and may run concurrently.

    Raises:
        ValueError: a cycle exists in the dependency graph.
    """
    by_id = {step.id: step for step in steps}
    remaining: dict[str, set[str]] = {s.id: set(s.depends_on) for s in steps}
    completed: set[str] = set()
    batches: list[list[PlanStep]] = []

    while remaining:
        ready_ids = [sid for sid, deps in remaining.items() if deps.issubset(completed)]
        if not ready_ids:
            unsorted = sorted(remaining.keys())
            raise ValueError(
                f"Cycle in plan dependencies; cannot order remaining steps: {unsorted}"
            )
        batches.append([by_id[sid] for sid in ready_ids])
        completed.update(ready_ids)
        for sid in ready_ids:
            del remaining[sid]

    return batches
