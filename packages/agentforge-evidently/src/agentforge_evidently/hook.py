"""`EvidentlyHook` — Evidently AI agent metrics + drift hook.

Per `Step` the hook adds one row to the runner's buffer; at
finish it builds an Evidently report from the buffer + writes
it to ``<report_dir>/<run_id>.json``.

Construction:

- ``EvidentlyHook(runner=<EvidentlyRunner>, ...)`` — direct
  injection (tests).
- ``EvidentlyHook.from_config(project=..., report_dir=...)``
  — lazy-imports the SDK + builds the production runner.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentforge_core.production.exceptions import ModuleError
from agentforge_core.production.run_context import current_run
from agentforge_core.values.state import RunResult, Step

if TYPE_CHECKING:
    from agentforge_evidently._runner import EvidentlyRunner


class EvidentlyHook:
    """Evidently-backed observability hook."""

    def __init__(
        self,
        *,
        runner: EvidentlyRunner,
        project: str = "agentforge",
        report_dir: str | Path = "./evidently-reports",
    ) -> None:
        if not project:
            msg = "project is required"
            raise ValueError(msg)
        self._runner = runner
        self._project = project
        self._report_dir = Path(report_dir)
        # Per-run buffer of dicts the hook accumulates as steps arrive
        # and drains at finish to build the report.
        self._buffers: dict[str, list[dict[str, Any]]] = {}

    @classmethod
    def from_config(
        cls,
        *,
        project: str = "agentforge",
        report_dir: str | Path = "./evidently-reports",
    ) -> EvidentlyHook:  # pragma: no cover — exercised only with `-m live`.
        """Build an `EvidentlyHook` backed by a real Evidently runner."""
        runner = _build_evidently_runner()
        return cls(runner=runner, project=project, report_dir=report_dir)

    @property
    def project(self) -> str:
        return self._project

    @property
    def report_dir(self) -> Path:
        return self._report_dir

    def __call__(self, payload: Step | RunResult) -> None:
        if isinstance(payload, Step):
            self._on_step(payload)
        else:
            self._on_finish(payload)

    def _on_step(self, step: Step) -> None:
        run_id = self._current_run_id()
        if run_id is None:
            return
        record = {
            "run_id": run_id,
            "iteration": step.iteration,
            "kind": step.kind,
            "cost_usd": float(step.cost_usd),
            "tokens_in": int(step.tokens_in),
            "tokens_out": int(step.tokens_out),
            "duration_ms": int(step.duration_ms),
            "has_tool_call": step.tool_call is not None,
        }
        self._buffers.setdefault(run_id, []).append(record)
        self._runner.add_record(record)

    def _on_finish(self, result: RunResult) -> None:
        records = self._buffers.pop(result.run_id, [])
        run_row = {
            "run_id": result.run_id,
            "iteration": -1,
            "kind": "__run__",
            "cost_usd": float(result.cost_usd),
            "tokens_in": int(result.tokens_in),
            "tokens_out": int(result.tokens_out),
            "duration_ms": int(result.duration_ms),
            "finish_reason": result.finish_reason,
            "n_steps": len(result.steps),
        }
        records.append(run_row)
        self._runner.add_record(run_row)
        report = self._runner.build_report(records, project=self._project)
        self._runner.write_report(report, path=self._report_dir / f"{result.run_id}.json")

    def close(self) -> None:
        """Release the underlying runner."""
        self._runner.close()
        self._buffers.clear()

    @staticmethod
    def _current_run_id() -> str | None:
        try:
            ctx = current_run()
        except RuntimeError:
            return None
        return ctx.run_id


def _build_evidently_runner() -> EvidentlyRunner:  # pragma: no cover — `-m live` only.
    """Lazy-import `evidently` and build the production runner."""
    try:
        import evidently  # noqa: F401, PLC0415
    except ImportError as exc:
        msg = (
            "evidently is not installed. Install via "
            "`pip install agentforge-evidently[evidently]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_evidently._runner import _EvidentlyClientRunner  # noqa: PLC0415

    return _EvidentlyClientRunner()


__all__ = ["EvidentlyHook"]
