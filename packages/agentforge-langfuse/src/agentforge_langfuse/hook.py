"""`LangfuseHook` — Langfuse trace dashboard emitter.

Implements the `StepHook + FinishHook` callable contract via
`__call__(payload)` dispatch (mirrors `OpenTelemetryHook`).

Trace shape:

- One trace per run, opened on the first step seen, keyed by
  ``run_id``. ``Step`` doesn't carry the run_id directly, so
  the hook reads it from `agentforge_core.runtime.current_run`
  (set by `Agent.run`'s `RunContext`).
- One span per step, named ``"step:<kind>"``, carrying the
  step's iteration, duration, and cost as metadata.
- A nested span per ``step.tool_call``, named
  ``"tool:<name>"`` with the redacted argument shape.
- Two scores at finish: ``"cost_usd"`` and ``"duration_ms"``.
- A `flush` call at finish so the trace lands in the
  dashboard without waiting for the SDK's batch interval.

Construction is two paths:

- ``LangfuseHook(runner=<LangfuseRunner>, ...)`` — direct
  injection.
- ``LangfuseHook.from_config(public_key=..., secret_key=...,
  host=...)`` — builds the production runner by lazy-importing
  ``langfuse``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentforge_core.production.exceptions import ModuleError
from agentforge_core.production.run_context import current_run
from agentforge_core.values.state import RunResult, Step

if TYPE_CHECKING:
    from agentforge_langfuse._runner import LangfuseRunner


_DEFAULT_REDACT = ("api_key", "password", "secret", "token", "authorization")


class LangfuseHook:
    """Langfuse-backed observability hook."""

    def __init__(
        self,
        *,
        runner: LangfuseRunner,
        trace_name_prefix: str = "agentforge",
        redact_fields: tuple[str, ...] | None = None,
    ) -> None:
        if not trace_name_prefix:
            msg = "trace_name_prefix is required"
            raise ValueError(msg)
        self._runner = runner
        self._trace_name_prefix = trace_name_prefix.rstrip(".")
        self._redact_fields = tuple(
            f.lower() for f in (redact_fields if redact_fields is not None else _DEFAULT_REDACT)
        )
        # Track which run_ids we've already opened a trace for.
        self._opened: set[str] = set()

    @classmethod
    def from_config(
        cls,
        *,
        public_key: str,
        secret_key: str,
        host: str | None = None,
        trace_name_prefix: str = "agentforge",
        redact_fields: tuple[str, ...] | None = None,
    ) -> LangfuseHook:  # pragma: no cover — exercised only with `-m live`.
        """Build a `LangfuseHook` backed by a real `langfuse.Langfuse` client."""
        runner = _build_langfuse_runner(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        return cls(
            runner=runner,
            trace_name_prefix=trace_name_prefix,
            redact_fields=redact_fields,
        )

    @property
    def redact_fields(self) -> tuple[str, ...]:
        return self._redact_fields

    def __call__(self, payload: Step | RunResult) -> None:
        """Hook entry point — dispatches on payload type."""
        if isinstance(payload, Step):
            self._on_step(payload)
        else:
            self._on_finish(payload)

    def _on_step(self, step: Step) -> None:
        run_id = self._current_run_id()
        if run_id is None:
            return  # No run context bound — caller fired the hook outside Agent.run.
        if run_id not in self._opened:
            self._runner.open_trace(
                name=f"{self._trace_name_prefix}.run",
                run_id=run_id,
                metadata={"agentforge.run_id": run_id},
            )
            self._opened.add(run_id)
        self._runner.add_span(
            trace_id=run_id,
            name=f"step:{step.kind}",
            metadata={
                "iteration": step.iteration,
                "duration_ms": step.duration_ms,
                "cost_usd": step.cost_usd,
                "tokens_in": step.tokens_in,
                "tokens_out": step.tokens_out,
            },
        )
        if step.tool_call is not None:
            self._runner.add_span(
                trace_id=run_id,
                name=f"tool:{step.tool_call.name}",
                metadata={"args": self._redact(dict(step.tool_call.arguments))},
            )

    def _on_finish(self, result: RunResult) -> None:
        run_id = result.run_id
        if run_id not in self._opened:
            # Hook never saw a step (zero-step run); open the trace
            # synthetically so the score has a home.
            self._runner.open_trace(
                name=f"{self._trace_name_prefix}.run",
                run_id=run_id,
                metadata={"agentforge.run_id": run_id, "synthetic": True},
            )
            self._opened.add(run_id)
        self._runner.add_score(
            trace_id=run_id,
            name="cost_usd",
            value=float(result.cost_usd),
            comment=f"finish_reason={result.finish_reason}",
        )
        self._runner.add_score(
            trace_id=run_id,
            name="duration_ms",
            value=float(result.duration_ms),
        )
        self._runner.flush(trace_id=run_id)
        self._opened.discard(run_id)

    def close(self) -> None:
        """Release the underlying runner."""
        self._runner.close()

    @staticmethod
    def _current_run_id() -> str | None:
        try:
            ctx = current_run()
        except RuntimeError:
            return None
        return ctx.run_id

    def _redact(self, args: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in args.items():
            if any(token in key.lower() for token in self._redact_fields):
                out[key] = "<redacted>"
            else:
                out[key] = value
        return out


def _build_langfuse_runner(  # pragma: no cover — exercised only with `-m live`.
    *,
    public_key: str,
    secret_key: str,
    host: str | None,
) -> LangfuseRunner:
    """Lazy-import `langfuse` and build a production runner."""
    try:
        from langfuse import Langfuse  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover — exercised only when SDK is missing
        msg = (
            "langfuse is not installed. Install via "
            "`pip install agentforge-langfuse[langfuse]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_langfuse._runner import _LangfuseClientRunner  # noqa: PLC0415

    kwargs: dict[str, Any] = {"public_key": public_key, "secret_key": secret_key}
    if host is not None:
        kwargs["host"] = host
    client = Langfuse(**kwargs)
    return _LangfuseClientRunner(client)


__all__ = ["LangfuseHook"]
