"""OpenTelemetry tracing for AgentForge — feat-009.

Public surface:
- `OpenTelemetryHook` — configures the SDK provider + OTLP exporter
  on construction, satisfies both `on_step` and `on_finish` hook
  contracts via `__call__(step_or_result)` dispatch.
"""

from __future__ import annotations

from agentforge_otel.hook import OpenTelemetryHook

__all__ = ["OpenTelemetryHook"]
