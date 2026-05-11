# feat-009: Observability

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-009 |
| **Title** | Observability — structured logging, distributed tracing (OpenTelemetry), and dashboard exporters |
| **Status** | shipped (Python — OTel only; vendor backends deferred) |
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

---

## Implementation status

**Status: shipped (Python, OTel only).** Landed across 7 chunks on
`feat/009-observability`. Vendor-specific dashboard packages
(Langfuse, Phoenix, Evidently, StatsD) deferred to follow-up
sub-feats — the spec's own thesis backs this: "OTel is the wire
format; any vendor that ingests OTel works without a vendor-
specific module."

| Chunk | Scope |
|---|---|
| 1 | Hook fan-out: `Agent(on_step=...)` accepts `Hook \| list[Hook]` and `on_step` actually fires (was accepted but never invoked under feat-001). Error isolation — bad hook logs WARN via `agentforge.observability` and the run continues. Sync + async hooks both supported. Steps fire on error paths too. |
| 2 | JSON log format — `JsonFormatter` + `install_json_formatter` in `agentforge-core/production/log_format.py`; `Agent.__init__` installs when `logging.format == "json"`. |
| 3 | `agentforge-core` adds `opentelemetry-api>=1.27`; new `agentforge_core/observability/tracing.py` with `get_tracer()`. |
| 4 | Framework span emission — `Agent.run` opens a root `agent.run` span with run_id / task / cost / token / duration / step-count attributes. |
| 5 | `agentforge-otel` new workspace member — `OpenTelemetryHook(endpoint=, service_name=, sample_rate=, redact_fields=)` configures the SDK + OTLP gRPC exporter on construction (idempotent; respects existing user provider). |
| 6 | `OpenTelemetryHook` satisfies both step + finish hook contracts via `__call__` dispatch; per-step events with token / cost / duration attributes; tool-call events with key-based arg redaction. End-to-end test via OTel's `InMemorySpanExporter` asserts the root span lands with the expected attribute + event tree. |
| 7 | This Implementation section + Runbook + CHANGELOG + roadmap + forward-ref sweep. |

### Deviations from this spec

- **Single PR scope is OTel only.** The four vendor packages
  (`agentforge-langfuse`, `agentforge-phoenix`, `agentforge-evidently`,
  `agentforge-statsd`) are deferred to follow-up sub-feats. Spec
  §4.4 lists them; the user opted to ship OTel first since it
  covers every collector that ingests OTLP (Datadog, Honeycomb,
  Jaeger, Grafana Tempo, SigNoz, New Relic, etc.).
- **Built-in spans landed only at the run boundary, not all the
  way down.** Spec §4.3 shows a full tree:
  ```
  agent.run → strategy.iteration → llm.call / tool.<name> / evaluator.<name>
  ```
  We ship `agent.run` as the root. The hook fans out step + tool-call
  events onto the active span, which gives a flattened version of
  the tree. Wiring `strategy.iteration` + `llm.call` +
  `evaluator.<name>` spans as proper children of `agent.run` is a
  follow-up — requires touching strategy / dispatch internals
  beyond this PR's scope. The current shape is still useful: every
  `agent.run` span carries finish_reason, cost, tokens, duration,
  and per-step / per-tool-call events.
- **Redaction is key-based, not field-content-based.** The hook
  matches the lower-cased argument key against a list of
  substrings (`api_key`, `password`, etc.); the value gets
  replaced wholesale. Content-based redaction (regex over the
  value text) is a follow-up.
- **Service-name default falls back to `"agentforge"`.** Spec
  hinted at deriving it from project name; we required the caller
  to specify it explicitly (sensible default, but explicit is
  better than guessing).

### What's *not* yet implemented

- **Vendor packages**: `agentforge-langfuse`, `agentforge-phoenix`,
  `agentforge-evidently`, `agentforge-statsd`. Each is a small
  follow-up that wraps its respective SDK in the same hook
  contract; OTel coverage covers the major bases until then.
- **`strategy.iteration` / `llm.call` / `tool.<name>` /
  `evaluator.<name>` child spans** as proper OTel spans (not just
  events). Requires instrumenting strategy internals + tool
  dispatch + the evaluator loop.
- **A2A trace propagation** across peer-agent calls (feat-014
  dependency).
- **Content-based PII redaction** (regex over arg values).
- **TypeScript port** of the whole feat-009 surface.

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented "how do I…" content. This is the canonical
home for the feature's runbook; feat-011 / feat-019 consume these
sections into scaffolded agent projects.

### How do I add observability to an agent?

For development — just `RunIdFilter` (auto-installed by `Agent`):

```python
import logging
from agentforge import Agent

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [run_id=%(run_id)s] %(levelname)s %(name)s: %(message)s")
async with Agent(model="bedrock:...") as agent:
    result = await agent.run("...")
# stdout: 2026-05-11 16:42:01 [run_id=01HX...] INFO agentforge: ...
```

For production — install OTel:

```bash
uv add agentforge-otel
```

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

### How do I emit JSON logs?

Set `logging.format: "json"` in `agentforge.yaml`:

```yaml
logging:
  level: "INFO"
  run_id_filter: true
  format: "json"
```

Or call `install_json_formatter()` explicitly:

```python
from agentforge_core import install_json_formatter
install_json_formatter()
```

Each log line becomes one JSON object: `{"ts": "...", "level":
"INFO", "logger": "agentforge.agent", "msg": "...", "run_id":
"01HX..."}`. Extra fields passed via
`logger.info(..., extra={"tool": "web_search"})` pass through.

### How do I fan out to multiple observability backends?

Pass a list of hooks. Each fires in registration order; one
hook's exception doesn't affect siblings.

```python
agent = Agent(
    model="...",
    on_step=[otel, my_custom_metrics_hook],
    on_finish=[otel, persist_run_summary],
)
```

A raising hook logs WARN via `agentforge.observability` and the
run continues. The framework's invariant per spec §4.3:
**observability must never break the run**.

### How do I write a custom hook?

The simplest shape — a callable that takes a `Step` (or
`RunResult` for `on_finish`):

```python
def metrics_hook(step):
    statsd.increment(f"agent.step.{step.kind}")
    if step.tool_call:
        statsd.increment(f"agent.tool.{step.tool_call.name}")

agent = Agent(model="...", on_step=metrics_hook)
```

Async is also supported — return a coroutine and it gets awaited:

```python
async def upload_step(step):
    await dashboard.post_step(step.model_dump())

agent = Agent(model="...", on_step=upload_step)
```

For a class-based observer that handles both step and finish,
make it callable with type dispatch (mirrors `OpenTelemetryHook`):

```python
class MyObserver:
    def __call__(self, payload):
        if isinstance(payload, Step):
            self._on_step(payload)
        else:
            self._on_finish(payload)

obs = MyObserver()
agent = Agent(model="...", on_step=obs, on_finish=obs)
```

### How do I redact secrets from traces?

`OpenTelemetryHook` redacts tool-call argument values whose keys
contain any of `api_key`, `password`, `secret`, `token`,
`authorization` (case-insensitive). Override the list:

```python
otel = OpenTelemetryHook(
    endpoint="http://otel-collector:4317",
    service_name="payments-agent",
    redact_fields=("api_key", "ssn", "card_number", "cvv"),
)
```

Match is substring-on-key — `"ssn"` redacts `"customer_ssn"`,
`"ssn_last4"`, etc. Values are replaced wholesale with
`<redacted>`.

For redaction of secrets that appear in step *content* (the LLM
output text, not the tool args), wrap your `on_step` hook with a
regex scrubber before passing it. Content-based redaction in the
hook itself is a follow-up.

### How do I keep observability cost low?

Three knobs:

```python
otel = OpenTelemetryHook(
    endpoint="...",
    service_name="...",
    sample_rate=0.1,         # only 10% of traces sampled
)
```

`sample_rate` uses OTel's `TraceIdRatioBased` sampler — every
span in a given trace inherits the trace-level decision, so a
sampled run keeps the full per-step / per-tool tree, while
unsampled runs emit nothing.

Sync vs async: heavy hook work blocks the agent loop. Push to
a queue / `asyncio.create_task` for fire-and-forget:

```python
async def upload(step):
    asyncio.create_task(dashboard.post_step(step.model_dump()))
```

### How do I see what's in `agent.run`'s span?

The root span attributes after the run completes:

- `agentforge.run_id`
- `agentforge.task`
- `agentforge.finish_reason` (completed / budget_exceeded / guardrail / error)
- `agentforge.cost_usd`
- `agentforge.tokens_in`, `agentforge.tokens_out`
- `agentforge.duration_ms`
- `agentforge.n_steps`

Each step the strategy emitted lands as an `agent.step` event on
the root span with `agentforge.step.iteration`, `kind`,
`cost_usd`, `tokens_in`, `tokens_out`, `duration_ms`. Tool calls
add an `agent.tool_call` event with the tool name and redacted
args.

### Which vendor can ingest these traces?

Anything that speaks OTLP — Datadog, Honeycomb, Jaeger, Grafana
Tempo, SigNoz, New Relic, AWS X-Ray (via the AWS OTel collector).
Point `endpoint=` at your collector's gRPC port (4317 by
default). No vendor-specific code needed.

Future first-party packages (`agentforge-langfuse`,
`agentforge-phoenix`, `agentforge-evidently`, `agentforge-statsd`)
will add LLM-specific dashboards on top of the OTel baseline once
shipped.

### When should I NOT add an observability hook?

- **In a tight loop where latency matters more than visibility.**
  Synchronous hooks run inline; even cheap ones add up across
  thousands of steps. Switch to async fire-and-forget.
- **For per-token telemetry.** Hooks fire per `Step`, not per
  token. Token-level streaming is a future capability (feat-003
  has the streaming surface).
- **As error-suppression.** Hooks catch their own exceptions so
  the run continues — but they don't get a chance to fix a broken
  agent. Don't move business logic into hooks.
