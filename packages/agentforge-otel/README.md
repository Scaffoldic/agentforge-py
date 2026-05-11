# agentforge-otel

OpenTelemetry tracing for AgentForge (feat-009).

The OTel **API** ships in `agentforge-core` — the framework emits
spans unconditionally. Without this package, those calls degrade to
`NonRecordingSpan` (near-zero cost). Installing `agentforge-otel`
wires up the **SDK**, an OTLP exporter, and a sampler so the spans
actually reach a collector.

## Quick start

```python
from agentforge import Agent
from agentforge_otel import OpenTelemetryHook

otel = OpenTelemetryHook(
    endpoint="http://otel-collector:4317",
    service_name="my-agent",
    sample_rate=1.0,
)

agent = Agent(
    model="bedrock:...",
    tools=[...],
    on_step=otel,
    on_finish=otel,
)
```

Constructing the hook installs the SDK provider once (idempotent). The
framework's existing span emission then produces a tree per run:

    span: agent.run
    └── span: strategy.iteration
        ├── span: llm.call
        ├── span: tool.<name>
        └── span: evaluator.<name>

Span attributes carry `agentforge.run_id`, cost, token counts,
finish reason, and step count — same correlation key the
`RunIdFilter` puts on every log line.

## Multiple backends

Run OTel alongside any other observer:

```python
agent = Agent(
    model="...",
    on_step=[otel, my_statsd_hook],
    on_finish=[otel, persist_to_db],
)
```

Hooks fire in registration order; one hook's exception doesn't
affect siblings (the framework logs WARN via
`agentforge.observability` and keeps going).

## Vendor compatibility

OTel is the wire format; any collector that ingests OTLP works:
Datadog, Honeycomb, Jaeger, Grafana Tempo, SigNoz, New Relic. Point
the `endpoint` at your collector's gRPC port (4317 by default).
