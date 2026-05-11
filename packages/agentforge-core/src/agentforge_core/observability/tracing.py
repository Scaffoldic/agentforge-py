"""`get_tracer` — OpenTelemetry tracer accessor for framework spans.

feat-009 §4.3 defines a span tree per run:

    span: agent.run
    └── span: strategy.iteration
        ├── span: llm.call
        ├── span: tool.<name>
        └── span: evaluator.<name>

The framework emits these spans unconditionally via the OTel API. When
no SDK provider is configured (the default), `start_as_current_span`
returns the no-op `NonRecordingSpan` and the cost is negligible. When
`agentforge-otel` configures a real provider, the same call sites
produce real spans + attributes that flow to the OTLP collector.

`SCOPE_NAME` is the OTel instrumentation scope used for every framework
span; `agentforge-otel` filters or routes on it.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.trace import Tracer

SCOPE_NAME = "agentforge"
"""Instrumentation scope name for every framework-emitted span."""


def get_tracer() -> Tracer:
    """Return the framework's tracer.

    Always safe to call — works whether or not an SDK provider is
    installed. The same `Tracer` instance is fine across the
    process; OTel handles thread/async safety internally.
    """
    return trace.get_tracer(SCOPE_NAME)
