"""`PipelineResult` — the locked output of `Pipeline.run()`.

feat-015 ships this as a frozen Pydantic value model. The runtime
stores it on the agent for the duration of one run (system prompt
addendum + ``pipeline_findings`` built-in tool) and optionally
records it as a single ``__pipeline`` claim when ``record_runs`` is
configured.

`findings` is a list of `Finding` Protocol-compatible objects (the
shipped variants from ``agentforge.findings`` all satisfy it). The
shape stays tolerant of custom finding subclasses.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PipelineResult(BaseModel):
    """Consolidated output of one `Pipeline.run()` call.

    Fields:
        findings: All findings emitted across every task, in the
            order each task completed. Task-failure entries (when
            ``on_task_error="continue"``) appear here too as
            ``SimpleFinding(category="pipeline.task_failure")``.
        task_durations_ms: Per-task wallclock duration in
            milliseconds.
        task_failures: Map of task name → error message for any
            task that raised. Empty when every task succeeded.
        total_cost_usd: Sum of ``cost_estimate_usd`` across all
            tasks that ran (the engine charges this against the
            agent's budget).
    """

    model_config = ConfigDict(frozen=True, strict=True)

    findings: tuple[Any, ...] = ()
    task_durations_ms: dict[str, int] = Field(default_factory=dict)
    task_failures: dict[str, str] = Field(default_factory=dict)
    total_cost_usd: float = Field(default=0.0, ge=0.0)
