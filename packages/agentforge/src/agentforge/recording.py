"""Run-recording hooks (feat-017).

Records every emitted `Step` and the final `RunResult` to a configured
`MemoryStore` so `agentforge run --replay <run-id>` and `agentforge
debug --replay <run-id>` can reconstruct a run deterministically.

Layout in the store (reserved categories):

- `category="__step"` — one claim per `Step`, payload carries every
  field on the frozen model so the step can be re-instantiated.
- `category="__eval"` — one claim per `EvalResult` from the run.
- `category="__run"` — one claim per run carrying the run-level
  summary (output, cost, tokens, duration, finish_reason).

The hook is opt-in: pass `Agent(record_runs=memory)` (or use
`agentforge run --record` from the CLI). Errors are isolated by
`Agent`'s existing `_safe_call_hook` wrapper — recording will never
break a run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.production.run_context import current_run
from agentforge_core.values.claim import Claim

if TYPE_CHECKING:
    from agentforge_core.values.pipeline import PipelineResult
    from agentforge_core.values.state import RunResult, Step

# Public category names. Tests, CLI, and external tooling can rely on
# these — they are part of the v0.1 on-disk contract.
STEP_CATEGORY = "__step"
EVAL_CATEGORY = "__eval"
RUN_CATEGORY = "__run"
PIPELINE_CATEGORY = "__pipeline"


class RecordRunHook:
    """Builds hooks that persist run telemetry to a `MemoryStore`.

    Single hook object exposes `.on_step` and `.on_finish` callables
    that `Agent` installs alongside any user-supplied hooks.
    """

    def __init__(
        self,
        *,
        memory: MemoryStore,
        project: str,
        agent_name: str,
    ) -> None:
        self._memory = memory
        self._project = project
        self._agent_name = agent_name

    async def on_step(self, step: Step) -> None:
        try:
            run_id = current_run().run_id
        except RuntimeError:
            # Outside Agent.run(); fall back to a sentinel so the
            # claim still persists. Tests that call the hook directly
            # exercise this branch.
            run_id = "unknown"
        await self._memory.put(
            Claim(
                run_id=run_id,
                project=self._project,
                agent=self._agent_name,
                category=STEP_CATEGORY,
                payload=_step_payload(step),
            )
        )

    async def on_finish(self, result: RunResult) -> None:
        await self._memory.put(
            Claim(
                run_id=result.run_id,
                project=self._project,
                agent=self._agent_name,
                category=RUN_CATEGORY,
                payload={
                    "output": _serializable(result.output),
                    "cost_usd": result.cost_usd,
                    "tokens_in": result.tokens_in,
                    "tokens_out": result.tokens_out,
                    "duration_ms": result.duration_ms,
                    "finish_reason": result.finish_reason,
                    "metadata": dict(result.metadata),
                },
            )
        )
        for eval_result in result.eval_scores:
            await self._memory.put(
                Claim(
                    run_id=result.run_id,
                    project=self._project,
                    agent=self._agent_name,
                    category=EVAL_CATEGORY,
                    payload=eval_result.model_dump(mode="json"),
                )
            )


def _step_payload(step: Step) -> dict[str, Any]:
    """Serialize a `Step` into a JSON-safe dict for storage."""
    return {
        "iteration": step.iteration,
        "kind": step.kind,
        "content": _serializable(step.content),
        "tool_call": step.tool_call.model_dump(mode="json") if step.tool_call else None,
        "tokens_in": step.tokens_in,
        "tokens_out": step.tokens_out,
        "cost_usd": step.cost_usd,
        "duration_ms": step.duration_ms,
        "timestamp": step.timestamp.isoformat(),
        "metadata": dict(step.metadata),
    }


def _serializable(value: Any) -> Any:
    """Pass-through for dicts/lists/scalars; coerce others to str."""
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _serializable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_serializable(v) for v in value]
    return str(value)


async def record_pipeline_result(
    *,
    memory: MemoryStore,
    run_id: str,
    project: str,
    agent_name: str,
    result: PipelineResult,
) -> None:
    """Persist a `PipelineResult` as one ``__pipeline`` claim.

    Replay reads this back and threads it into `Agent.run`'s
    ``replay_pipeline`` kwarg so the deterministic tasks don't
    re-execute (side-effect-bearing tasks would double-run).
    """
    await memory.put(
        Claim(
            run_id=run_id,
            project=project,
            agent=agent_name,
            category=PIPELINE_CATEGORY,
            payload={
                "findings": [_finding_payload(f) for f in result.findings],
                "task_durations_ms": dict(result.task_durations_ms),
                "task_failures": dict(result.task_failures),
                "total_cost_usd": result.total_cost_usd,
            },
        )
    )


def _finding_payload(f: Any) -> dict[str, Any]:
    dump = getattr(f, "model_dump", None)
    if callable(dump):
        result = dump(mode="json")
        if isinstance(result, dict):
            return result
    to_dict = getattr(f, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        if isinstance(result, dict):
            return result
    return {
        "severity": getattr(f, "severity", None),
        "category": getattr(f, "category", None),
        "message": getattr(f, "message", None),
    }


__all__ = [
    "EVAL_CATEGORY",
    "PIPELINE_CATEGORY",
    "RUN_CATEGORY",
    "STEP_CATEGORY",
    "RecordRunHook",
    "record_pipeline_result",
]
