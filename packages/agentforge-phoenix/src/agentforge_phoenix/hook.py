"""`PhoenixHook` — Arize Phoenix dashboard emitter.

Implements the `StepHook + FinishHook` callable contract via
`__call__(payload)` dispatch.

Logged events (per Phoenix project):

- ``log_step`` — once per `Step`.
- ``log_tool_call`` — once per `step.tool_call` (redacted args).
- ``log_run`` — once per `RunResult` at finish.

Construction:

- ``PhoenixHook(runner=<PhoenixRunner>, ...)`` — direct injection.
- ``PhoenixHook.from_config(endpoint=..., project_name=...)`` —
  lazy-imports the SDK + builds the production runner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentforge_core.production.exceptions import ModuleError
from agentforge_core.production.run_context import current_run
from agentforge_core.values.state import RunResult, Step

if TYPE_CHECKING:
    from agentforge_phoenix._runner import PhoenixRunner


_DEFAULT_REDACT = ("api_key", "password", "secret", "token", "authorization")


class PhoenixHook:
    """Phoenix-backed observability hook."""

    def __init__(
        self,
        *,
        runner: PhoenixRunner,
        project_name: str = "agentforge",
        redact_fields: tuple[str, ...] | None = None,
    ) -> None:
        if not project_name:
            msg = "project_name is required"
            raise ValueError(msg)
        self._runner = runner
        self._project_name = project_name
        self._redact_fields = tuple(
            f.lower() for f in (redact_fields if redact_fields is not None else _DEFAULT_REDACT)
        )

    @classmethod
    def from_config(
        cls,
        *,
        endpoint: str,
        project_name: str = "agentforge",
        redact_fields: tuple[str, ...] | None = None,
    ) -> PhoenixHook:  # pragma: no cover — exercised only with `-m live`.
        """Build a `PhoenixHook` backed by a real Phoenix client."""
        runner = _build_phoenix_runner(endpoint=endpoint, project_name=project_name)
        return cls(
            runner=runner,
            project_name=project_name,
            redact_fields=redact_fields,
        )

    @property
    def project_name(self) -> str:
        return self._project_name

    @property
    def redact_fields(self) -> tuple[str, ...]:
        return self._redact_fields

    def __call__(self, payload: Step | RunResult) -> None:
        if isinstance(payload, Step):
            self._on_step(payload)
        else:
            self._on_finish(payload)

    def _on_step(self, step: Step) -> None:
        run_id = self._current_run_id()
        if run_id is None:
            return
        self._runner.log_step(
            run_id=run_id,
            iteration=step.iteration,
            kind=step.kind,
            metadata={
                "duration_ms": step.duration_ms,
                "cost_usd": step.cost_usd,
                "tokens_in": step.tokens_in,
                "tokens_out": step.tokens_out,
            },
        )
        if step.tool_call is not None:
            self._runner.log_tool_call(
                run_id=run_id,
                tool_name=step.tool_call.name,
                args_redacted=self._redact(dict(step.tool_call.arguments)),
            )

    def _on_finish(self, result: RunResult) -> None:
        self._runner.log_run(
            run_id=result.run_id,
            attributes={
                "finish_reason": result.finish_reason,
                "cost_usd": float(result.cost_usd),
                "tokens_in": int(result.tokens_in),
                "tokens_out": int(result.tokens_out),
                "duration_ms": int(result.duration_ms),
                "n_steps": len(result.steps),
            },
        )

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


def _build_phoenix_runner(  # pragma: no cover — exercised only with `-m live`.
    *,
    endpoint: str,
    project_name: str,
) -> PhoenixRunner:
    """Lazy-import `phoenix` and build a production runner."""
    try:
        import phoenix as px  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "arize-phoenix is not installed. Install via "
            "`pip install agentforge-phoenix[phoenix]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_phoenix._runner import _PhoenixClientRunner  # noqa: PLC0415

    client = px.Client(endpoint=endpoint)
    return _PhoenixClientRunner(client, project_name=project_name)


__all__ = ["PhoenixHook"]
