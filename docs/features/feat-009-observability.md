# feat-009: Observability

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-009 |
| **Title** | Observability — structured logging, distributed tracing (OpenTelemetry), and dashboard exporters |
| **Status** | proposed |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.2 |
| **Languages** | both |
| **Module package(s)** | `agentforge` (built-in stdlib filter), `agentforge-otel`, `agentforge-langfuse`, `agentforge-phoenix` |
| **Depends on** | feat-001, feat-007 (run_id) |
| **Blocks** | none |

---

## 1. Why this feature

You can't run an agent in production without observability. The first incident
will demand: which run misbehaved, how much did it cost, what tools did it
call, why did it terminate, where did time go. Without instrumentation, those
answers require print debugging in front of an angry user.

This feature covers the three pillars:

- **Structured logging** — every log line carries `run_id` so a single agent
  run is greppable across services.
- **Distributed tracing** — OpenTelemetry spans for the full call tree
  (agent run → strategy iteration → LLM call → tool call → evaluator),
  propagated across A2A boundaries (feat-014) so a request that fans out to
  a peer agent has a single end-to-end trace.
- **Metrics & dashboards** — counters / histograms emitted via OTel; turnkey
  exporters for Langfuse, Phoenix (Arize), and StatsD.

Most frameworks ship "observability" as an afterthought: bring your own
logger, integrate with Datadog yourself, hope nothing breaks. The result is
that every team's observability story is bespoke, comparing two agents'
performance is impossible, and the integration always lags the product.

## 2. Why it must ship as framework

- **`run_id` is the correlation key.** It's set in feat-007; observability
  hooks have to consume it consistently or correlation breaks.
- **`on_step` and `on_finish` hooks are the framework's instrumentation
  surface.** If we don't define them, every observability backend defines
  its own integration point and the surface fragments.
- **Out-of-the-box stdlib logging with `run_id` is a baseline that every
  agent gets for free.** Production-ready *means* knowing what your agent
  did, even on day 1, even with no external observability stack.
- **OTel integration as a module** lets agents adopt it without changing
  agent code; the alternative is each agent writing its own tracer.
- **Without framework ownership:** no comparable metrics across agents, no
  shared dashboards, observability becomes per-team.

## 3. How derived agents benefit

- **Day 0 — structured logs with `run_id` for free.** Default `RunIdFilter`
  attached to root logger; every log line correlatable.
- **Day 30 — OTel adoption is a `pip install`.** `agentforge-otel`
  auto-creates spans for run, strategy, LLM call, tool call. Existing OTel
  collector picks them up.
- **Day 60 — Langfuse / Phoenix / Evidently dashboards.** `pip install
  agentforge-langfuse` (or any other backend); LLM calls, tool calls,
  evaluator scores stream to the dashboard. No agent code change. Multiple
  backends can run concurrently — emit to OTel collector *and* Langfuse
  *and* a custom in-house tool, all from the same run.
- **Day 90 — bespoke observer in 10 lines.** Implement the hook contract,
  decorate it with `@register("hooks", "my-statsd")`, and reference it from
  YAML. The framework calls it on every step alongside the shipped
  observers.
- **Day 120 — incident.** "Run X did Y." Search by `run_id` across logs,
  traces, claims, evaluation results — same id everywhere.
- **Vendor-agnostic.** OTel is the wire format; any vendor that ingests
  OTel (Datadog, Honeycomb, New Relic, Jaeger, Tempo, SigNoz, Grafana
  Cloud) works without a vendor-specific module.

## 4. Feature specifications

### 4.1 User-facing experience

```python
from agentforge import Agent

# Default: stdlib logging with run_id filter
agent = Agent(model="...", tools=[...])

# Add OTel
from agentforge_otel import OpenTelemetryHook
agent = Agent(
    model="...", tools=[...],
    on_step=OpenTelemetryHook(),
    on_finish=OpenTelemetryHook(),
)

# Or via config (preferred)
# agentforge.yaml:
# modules:
#   observability:
#     - name: otel
#       config:
#         endpoint: "http://otel-collector:4317"
#         service_name: "my-agent"

# Custom hook
def metrics_hook(step):
    statsd.increment(f"agent.tool.{step.tool_call.name}")

agent = Agent(model="...", tools=[...], on_step=metrics_hook)
```

### 4.2 Public API / contract

```python
# agentforge_core/contracts/hooks.py — locked
StepHook = Callable[[Step], Awaitable[None] | None]
FinishHook = Callable[[RunResult], Awaitable[None] | None]

# agentforge_core/observability/run_id_filter.py
class RunIdFilter(logging.Filter):
    """Attaches `run_id` from ContextVar onto every LogRecord.

    Auto-installed on root logger by Agent.__init__ (idempotent).
    Disable via logging.run_id_filter: false in agentforge.yaml.
    """
    def filter(self, record: logging.LogRecord) -> bool: ...

# agentforge_otel/hook.py
class OpenTelemetryHook:
    def __init__(self, *, endpoint: str | None = None,
                 service_name: str = "agentforge",
                 tracer: Tracer | None = None) -> None: ...

    async def __call__(self, step_or_result: Step | RunResult) -> None: ...

class HookRegistry:
    """The framework supports lists of hooks for on_step and on_finish."""
    def register_step_hook(self, hook: StepHook) -> None: ...
    def register_finish_hook(self, hook: FinishHook) -> None: ...
```

### 4.3 Internal mechanics

```
Agent.run(task)
   │
   ├── for each step appended to state.steps:
   │       for hook in step_hooks:    fire-and-forget if async
   │           hook(step)
   │
   └── on completion:
       for hook in finish_hooks:
           await hook(result)         awaited; errors logged but not raised
```

Hooks run in registration order. Errors in hooks are logged (with `run_id`)
and swallowed — observability must never break the run.

**Distributed trace structure.** OTel spans form a tree per run. Span
attributes carry the structured context; trace context propagates over A2A
calls so multi-agent flows have a single trace.

```
trace: <trace_id>
└── span: agent.run                 [run_id=X, agent.name=pr-reviewer]
    ├── span: guardrail.input       [validators=2, action=allow]      ← feat-018
    ├── span: strategy.iteration    [iter=1]
    │   ├── span: llm.call          [provider=anthropic, model=...,
    │   │                              tokens_in=N, tokens_out=M, cost_usd=0.012]
    │   ├── span: guardrail.tool    [tool=web_search, action=allow]   ← feat-018
    │   └── span: tool.web_search   [duration_ms=1234]
    ├── span: strategy.iteration    [iter=2]
    │   └── span: a2a.call          [peer=fact-checker, parent_run_id=X]
    │       └── (remote trace continues with peer's run_id as child)
    ├── span: guardrail.output      [validators=2, action=redact]     ← feat-018
    └── span: evaluator.faithfulness [score=0.91, cost_usd=0.003]
```

`agentforge-otel` configures the tracer provider, exporter, and resource
attributes; subsequent spans are emitted automatically by the framework's
`on_step` / `on_finish` hooks plus internal instrumentation in
`Agent.run()`. Custom hooks add their own spans by reading `current_run()`
(feat-007) for the `run_id`.

### 4.4 Module packaging

| Package | Provides |
|---|---|
| `agentforge` | `RunIdFilter` + structured stdlib logging (always installed) |
| `agentforge-otel` | OpenTelemetry tracing + metrics emitter (vendor-agnostic; works with Datadog, Honeycomb, Jaeger, Grafana Tempo, etc.) |
| `agentforge-langfuse` | Langfuse trace dashboard (LLM-focused) |
| `agentforge-phoenix` | Phoenix / Arize dashboard |
| `agentforge-evidently` | Evidently AI — agent metrics + drift monitoring |
| `agentforge-statsd` | StatsD metrics emitter |
| **custom** | Implement the hook contract; register via `@register("hooks", "<name>")` or entry point `agentforge.hooks` |

**Multiple backends concurrently.** A team can run, e.g., OTel (for ops
dashboards), Langfuse (for LLM-quality review), and a custom statsd hook
(for billing) all in the same agent. Each is configured under
`modules.observability` as a list; hooks fan out at the framework's
`on_step` / `on_finish` points.

### 4.5 Configuration

```yaml
logging:
  level: "INFO"
  run_id_filter: true
  format: "json"             # "json" | "text"

# Multiple observability backends — fan out at every hook point.
modules:
  observability:
    - name: otel
      config:
        endpoint: "http://otel-collector:4317"
        service_name: "my-agent"
        sample_rate: 1.0

    - name: langfuse
      config:
        public_key: "${LANGFUSE_PUBLIC_KEY}"
        secret_key: "${LANGFUSE_SECRET_KEY}"

    - name: my-statsd                      # custom — registered by the agent
      config:
        host: "statsd.internal"
        prefix: "agentforge.pr-reviewer"
```

```python
# Custom hook — register from your agent's code.
from agentforge import register
import statsd

@register("hooks", "my-statsd")
class MyStatsd:
    def __init__(self, host: str, prefix: str):
        self._client = statsd.StatsClient(host)
        self._prefix = prefix

    async def on_step(self, step):
        self._client.incr(f"{self._prefix}.step.{step.kind}")

    async def on_finish(self, result):
        self._client.timing(f"{self._prefix}.duration_ms", result.duration_ms)
        self._client.gauge(f"{self._prefix}.cost_usd", result.cost_usd)
```

## 5. Plug-and-play & upgrade story

`agentforge add module otel` installs and wires. Removing is `agentforge
remove module otel`. Each backend module versions independently behind the
hook contract.

Upgrade safety: hook signature locked; hooks may grow optional context kwargs
behind defaults. Custom user hooks survive minor framework bumps.

## 6. Cross-language parity

`RunIdFilter` ↔ pino transformer (TS). OTel SDK exists in both languages —
hook implementations idiomatic per language.

## 7. Test strategy

- **`run_id` propagation:** assert every emitted log line carries the right
  id, including across nested async tasks and tool subprocesses.
- **Hook error isolation:** raising in a hook does not crash the run.
- **OTel span shape:** snapshot test against an in-memory OTLP exporter.
- **Performance overhead:** observability adds &lt; 5% to total run latency
  (benchmarked).

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Hook latency dragging the run | Async hooks run concurrently with strategy; sync hooks run inline; document the cost |
| Sensitive data leaking into traces (PII in tool args) | Field-level redaction config; `redact: ["api_key", "password"]` mapping |
| OTel service name collision across agents | `service_name` required; default derived from project name |
| What about Datadog APM specifically? | Use the OTel→Datadog exporter; native module only if user demand justifies |
| Sampling strategy for high-throughput agents | Configurable rate; head-based sampling default |

## 9. Out of scope

- Building a custom dashboard. We ship hooks; dashboards live elsewhere.
- Per-tool latency budgeting. Out of scope; metrics enable it but the
  policy belongs in the agent, not the framework.
- Automatic anomaly detection / alerting. The metrics are emitted; alerts
  are configured in the user's existing observability stack.

## 10. References

- [`architecture.md`](../design/architecture.md) §7
- feat-001, feat-007 (`run_id`)
- Archived: `docs/archive/cr/CR-010-run-id-context-propagation.md`
