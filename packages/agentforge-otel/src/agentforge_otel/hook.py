"""`OpenTelemetryHook` — SDK setup + per-step/per-finish hook impl.

Construction installs the OTel SDK tracer provider with an OTLP gRPC
exporter and a `TraceIdRatioBased` sampler. Idempotent — repeat
construction reuses the existing provider.

The hook itself satisfies both step and finish hook contracts via
`__call__(payload)`:
- `Step` -> annotate the current span (run span or whatever's active)
  with per-step attributes.
- `RunResult` -> the run span has already been closed by `Agent.run`'s
  context manager; the hook just adds a final summary log via the
  `agentforge.observability` logger for callers that want a compact
  per-run line in their logs.

For arg redaction: the hook scrubs values whose keys match
`redact_fields` (case-insensitive substring match) before adding tool
call args as span attributes.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

from agentforge_core.values.state import RunResult, Step
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

_log = logging.getLogger("agentforge.observability")

_DEFAULT_REDACT = ("api_key", "password", "secret", "token", "authorization")

# Module-level lock so concurrent hook instantiations don't race on
# the global tracer provider. The "installed" flag lives on a mutable
# list to avoid a `global` declaration (PLW0603).
_setup_lock = threading.Lock()
_provider_installed: list[bool] = [False]


class OpenTelemetryHook:
    """Configures OTel SDK on construction; satisfies StepHook + FinishHook.

    Args:
        endpoint: OTLP gRPC endpoint (e.g. `http://otel-collector:4317`).
            Defaults to the OTel SDK's own env-var defaults
            (`OTEL_EXPORTER_OTLP_ENDPOINT`).
        service_name: Resource attribute under `service.name`. Required.
        sample_rate: `TraceIdRatioBased` rate in [0.0, 1.0]. Default 1.0
            (every trace sampled).
        redact_fields: Substring matches for sensitive field names.
            Defaults to common API-key / password / token names; pass
            your own to override.
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        service_name: str = "agentforge",
        sample_rate: float = 1.0,
        redact_fields: tuple[str, ...] | None = None,
        redact_value_patterns: tuple[str, ...] | None = None,
    ) -> None:
        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError(f"sample_rate must be in [0, 1]; got {sample_rate}")
        if not service_name:
            raise ValueError("service_name is required")

        self._service_name = service_name
        self._endpoint = endpoint
        self._sample_rate = sample_rate
        self._redact_fields = tuple(
            f.lower() for f in (redact_fields if redact_fields is not None else _DEFAULT_REDACT)
        )
        # feat-009 v0.3 polish: content-based PII redaction. Patterns
        # are compiled once at construction so per-step redaction
        # stays cheap. Default None — content-based redaction is
        # opt-in.
        self._redact_value_patterns: tuple[re.Pattern[str], ...] = (
            tuple(re.compile(p) for p in redact_value_patterns)
            if redact_value_patterns is not None
            else ()
        )
        _ensure_provider(
            service_name=service_name,
            endpoint=endpoint,
            sample_rate=sample_rate,
        )

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def redact_fields(self) -> tuple[str, ...]:
        return self._redact_fields

    @property
    def redact_value_patterns(self) -> tuple[re.Pattern[str], ...]:
        return self._redact_value_patterns

    def __call__(self, payload: Step | RunResult) -> None:
        """Hook entry point — dispatches on payload type."""
        if isinstance(payload, Step):
            self._on_step(payload)
        else:
            self._on_finish(payload)

    # ------------------------------------------------------------------
    # Step handling — annotate the current span.
    # ------------------------------------------------------------------

    def _on_step(self, step: Step) -> None:
        span = trace.get_current_span()
        # Span is the no-op NonRecordingSpan when nothing is active —
        # safe to call set_attribute on it (it just discards).
        span.add_event(
            "agent.step",
            attributes={
                "agentforge.step.iteration": step.iteration,
                "agentforge.step.kind": step.kind,
                "agentforge.step.cost_usd": step.cost_usd,
                "agentforge.step.tokens_in": step.tokens_in,
                "agentforge.step.tokens_out": step.tokens_out,
                "agentforge.step.duration_ms": step.duration_ms,
            },
        )
        if step.tool_call is not None:
            span.add_event(
                "agent.tool_call",
                attributes={
                    "agentforge.tool.name": step.tool_call.name,
                    "agentforge.tool.args": self._redact(dict(step.tool_call.arguments)),
                },
            )

    # ------------------------------------------------------------------
    # Finish handling — the run span already closed; log a summary.
    # ------------------------------------------------------------------

    def _on_finish(self, result: RunResult) -> None:
        _log.info(
            "run %s finished: %s (cost=$%.4f, tokens_in=%d, tokens_out=%d, steps=%d, %dms)",
            result.run_id,
            result.finish_reason,
            result.cost_usd,
            result.tokens_in,
            result.tokens_out,
            len(result.steps),
            result.duration_ms,
        )

    # ------------------------------------------------------------------
    # Redaction helper.
    # ------------------------------------------------------------------

    def _redact(self, args: dict[str, Any]) -> str:
        """Stringify a dict for span attribution, masking sensitive
        keys *and* values matching configured regex patterns.

        Two redaction passes:
        1. Key-based: case-insensitive substring match on the field
           name against `redact_fields` (e.g. ``api_key``,
           ``password``). The whole value gets masked.
        2. Content-based (feat-009 v0.3 polish): for string values
           that survived the key check, run each pattern in
           `redact_value_patterns` against the stringified value;
           any match masks the whole value.

        Span attributes accept primitives + lists thereof; we render
        the dict to a compact ``k=v`` form rather than fight the
        schema.
        """
        parts: list[str] = []
        for key, value in args.items():
            if any(token in key.lower() for token in self._redact_fields):
                parts.append(f"{key}=<redacted>")
                continue
            if self._value_matches_pattern(value):
                parts.append(f"{key}=<redacted>")
                continue
            parts.append(f"{key}={value!r}")
        return ", ".join(parts)

    def _value_matches_pattern(self, value: Any) -> bool:
        """True if any configured regex pattern matches the value
        text. Non-string values are stringified first so payloads
        like ``42``, ``True``, or nested dicts are still scanned."""
        if not self._redact_value_patterns:
            return False
        text = value if isinstance(value, str) else str(value)
        return any(p.search(text) for p in self._redact_value_patterns)


def _ensure_provider(
    *,
    service_name: str,
    endpoint: str | None,
    sample_rate: float,
) -> None:
    """Install the SDK provider + OTLP exporter once per process.

    Idempotent: subsequent calls (with potentially-different config)
    keep the first-installed provider. Re-installing would silently
    drop spans already in-flight on the previous provider, so we
    don't do that — first wins.
    """
    with _setup_lock:
        if _provider_installed[0]:
            return
        # If the user has already installed a TracerProvider themselves
        # (rare but possible — they wired OTel manually), respect it.
        existing = trace.get_tracer_provider()
        if isinstance(existing, TracerProvider):
            _provider_installed[0] = True
            return
        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(
            resource=resource,
            sampler=TraceIdRatioBased(sample_rate),
        )
        exporter_kwargs: dict[str, Any] = {}
        if endpoint is not None:
            exporter_kwargs["endpoint"] = endpoint
        exporter = OTLPSpanExporter(**exporter_kwargs)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _provider_installed[0] = True
