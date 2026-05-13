"""`StatsdHook` — StatsD metrics emitter for AgentForge.

Implements the `StepHook + FinishHook` callable contract via
`__call__(payload)` dispatch (mirrors `OpenTelemetryHook`).
Emits one counter + optional timing per step and a finish
summary with counters, gauges, and a run-level timing.

Metrics shape::

    <prefix>.step.<kind>            counter +1
    <prefix>.step.duration_ms       timing  (only when > 0)
    <prefix>.tool.<name>            counter +1 (when step.tool_call set)
    <prefix>.run.finish.<reason>    counter +1
    <prefix>.run.duration_ms        timing
    <prefix>.run.cost_usd           gauge
    <prefix>.run.tokens_in          gauge
    <prefix>.run.tokens_out         gauge

Construction is two paths:

- ``StatsdHook(runner=<StatsdRunner>, prefix="...")`` — direct
  injection. Used in tests with `FakeStatsdRunner`.
- ``StatsdHook.from_config(host=..., port=..., prefix=...)`` —
  builds the production `_StatsClientRunner` by lazy-importing
  the ``statsd`` SDK. Raises `ModuleError` with pip
  remediation when the SDK is missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.state import RunResult, Step

if TYPE_CHECKING:
    from agentforge_statsd._runner import StatsdRunner


class StatsdHook:
    """StatsD-backed observability hook."""

    def __init__(self, *, runner: StatsdRunner, prefix: str = "agentforge") -> None:
        if not prefix:
            msg = "prefix is required (e.g. 'agentforge.my-agent')"
            raise ValueError(msg)
        self._runner = runner
        self._prefix = prefix.rstrip(".")

    @classmethod
    def from_config(
        cls,
        *,
        host: str = "127.0.0.1",
        port: int = 8125,
        prefix: str = "agentforge",
    ) -> StatsdHook:
        """Build a `StatsdHook` backed by a real `statsd.StatsClient`."""
        runner = _build_statsd_runner(host=host, port=port)
        return cls(runner=runner, prefix=prefix)

    @property
    def prefix(self) -> str:
        return self._prefix

    def __call__(self, payload: Step | RunResult) -> None:
        """Hook entry point — dispatches on payload type."""
        if isinstance(payload, Step):
            self._on_step(payload)
        else:
            self._on_finish(payload)

    def _on_step(self, step: Step) -> None:
        self._runner.incr(f"{self._prefix}.step.{step.kind}")
        if step.duration_ms > 0:
            self._runner.timing(f"{self._prefix}.step.duration_ms", float(step.duration_ms))
        if step.tool_call is not None:
            self._runner.incr(f"{self._prefix}.tool.{step.tool_call.name}")

    def _on_finish(self, result: RunResult) -> None:
        self._runner.incr(f"{self._prefix}.run.finish.{result.finish_reason}")
        self._runner.timing(f"{self._prefix}.run.duration_ms", float(result.duration_ms))
        self._runner.gauge(f"{self._prefix}.run.cost_usd", float(result.cost_usd))
        self._runner.gauge(f"{self._prefix}.run.tokens_in", float(result.tokens_in))
        self._runner.gauge(f"{self._prefix}.run.tokens_out", float(result.tokens_out))

    def close(self) -> None:
        """Release the underlying runner's socket / connection."""
        self._runner.close()


def _build_statsd_runner(*, host: str, port: int) -> StatsdRunner:
    """Lazy-import `statsd` and build a production runner.

    Splitting this out keeps the SDK optional: bare
    ``pip install agentforge-statsd`` works (fake runner only),
    while ``pip install agentforge-statsd[statsd]`` enables the
    production path.
    """
    try:
        import statsd  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover — exercised only when SDK is missing
        msg = (
            "statsd is not installed. Install via "
            "`pip install agentforge-statsd[statsd]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_statsd._runner import _StatsClientRunner  # noqa: PLC0415

    client = statsd.StatsClient(host=host, port=port)
    return _StatsClientRunner(client)


__all__ = ["StatsdHook"]
