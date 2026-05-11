"""Observability primitives — tracer helper, span attribute helpers.

The OpenTelemetry **API** ships in core; the **SDK** + exporter ship
in the optional `agentforge-otel` package. Without the SDK, all
`tracer.start_*` calls degrade to the no-op `NonRecordingTracer` —
near-zero cost. Consumers that want real spans install
`agentforge-otel` and construct an `OpenTelemetryHook` (which
configures the SDK provider once).
"""

from __future__ import annotations

from agentforge_core.observability.tracing import (
    SCOPE_NAME,
    get_tracer,
)

__all__ = ["SCOPE_NAME", "get_tracer"]
