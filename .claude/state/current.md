---
feature: feat-009-observability
state: implementing
branch: feat/009-observability
started_at: 2026-05-11T16:30
last_milestone_at: 2026-05-11T16:30
last_shipped: feat-006 (Evaluators) shipped via PR #14 @ 09ab1cf
blocker: null
flags_for_user: []
---

## Active feature

[`feat-009 — Observability`](../../docs/features/feat-009-observability.md)

Deps: feat-001 ✓, feat-007 ✓ (run_id).

User decision (2026-05-11): single PR, **Option B** scope —
framework wiring + JSON logs + `agentforge-otel` package. Vendor-
specific packages (`-langfuse`, `-phoenix`, `-evidently`, `-statsd`)
deferred to follow-up features. Spec's own thesis backs this: OTel
is the wire format; every major vendor (Datadog, Honeycomb, Jaeger,
Grafana Tempo, SigNoz, New Relic) ingests OTel without a vendor-
specific module.

## Scope

Already shipped:

| Piece | Status |
|---|---|
| `RunIdFilter` + `install_run_id_filter` | ✓ feat-007 |
| `Agent(on_step=..., on_finish=...)` kwargs accepted | ✓ feat-001 |
| `current_run()` for run_id correlation | ✓ feat-007 |

This PR ships:

| Piece | Where |
|---|---|
| **`on_step` actually fired** per appended step | `agentforge/agent.py` |
| **List-of-hooks fan-out** — accept `StepHook \| list[StepHook]` | `agentforge/agent.py` |
| **Hook error isolation** — bad hook logs + swallows, doesn't crash run | `agentforge/agent.py` |
| **Async hook support** — both `on_step` and `on_finish` await if awaitable | `agentforge/agent.py` |
| **JSON log format option** via `logging.format` config | `agentforge/agent.py` + `agentforge/config` |
| **`agentforge-otel`** new workspace package | `packages/agentforge-otel/` |
| OTel tracer setup (provider + OTLP exporter + resource attrs) | inside new package |
| `OpenTelemetryHook` — implements both `on_step` and `on_finish` shapes | inside new package |
| Framework-emitted spans: `agent.run`, `strategy.iteration`, `llm.call`, `tool.call`, `evaluator.<name>` | inside new package + Agent.run instrumentation |
| Configurable sampling, service name, endpoint, redact-fields list | inside new package |

## Design choices

- **`StepHook` / `FinishHook` accept a single callable OR a list**
  via a Union type on the constructor. Internal storage always
  normalises to a list; firing iterates the list.

- **Hook error isolation**: catch any exception inside the
  per-hook call site; log via the `agentforge.observability`
  logger at WARN with the run_id, hook name, and exception type;
  do NOT raise. "Observability must never break the run" is the
  spec's invariant.

- **Async vs sync hooks**: detect `__await__` on the return value
  (existing pattern in `_fire_finish`) and await; sync hooks run
  inline. Document the latency cost.

- **JSON logging format** is provided by a `JsonFormatter`
  attached to the root logger's `StreamHandler` when
  `logging.format = "json"` in config. Defaults to "text" (current
  behaviour). The formatter emits `{"ts", "level", "msg",
  "run_id", "logger", ...extra}`.

- **`agentforge-otel` layout** mirrors `agentforge-bedrock` /
  `agentforge-memory-sqlite`. Dependency: `opentelemetry-api`,
  `opentelemetry-sdk`, `opentelemetry-exporter-otlp`.

- **OpenTelemetryHook** is a single class that satisfies both
  step and finish hook contracts via `__call__(step_or_result)`
  dispatch on type. Internally calls a private `_emit_step` /
  `_emit_finish`.

- **Built-in spans**: instrument `Agent.run` (root span) +
  `strategy.iteration` + `llm.call` + `tool.call` +
  `evaluator.<name>`. Implementation strategy: use OTel context
  propagation manually inside `Agent.run` and the strategies'
  dispatch points; spans use the active tracer when an OTel hook
  is registered, otherwise no-op. Use a `tracer = trace.get_tracer(
  "agentforge")` pattern — OTel's SDK no-ops cleanly when no
  provider is set, so the framework can call `tracer.start_as_current_span`
  unconditionally and the cost is near-zero when OTel is absent.

  **Trade-off**: this means `opentelemetry-api` becomes a
  transitive dependency of `agentforge` (not just `agentforge-otel`)
  — but it's a tiny, stable, pure-Python package. Alternative is
  conditional imports per call site, which is uglier.

- **Field redaction** for sensitive args (api_key, password, etc.)
  via a `redact_fields: list[str]` config on the OTel hook.
  Default: `["api_key", "password", "secret", "token"]`. Tool
  call args get redacted before being added as span attributes.

- **Sampling** via OTel's `TraceIdRatioBased` sampler;
  `sample_rate` config in `[0, 1]`.

- **Vendor packages deferred**: `agentforge-langfuse`,
  `agentforge-phoenix`, `agentforge-evidently`, `agentforge-statsd`
  each become their own backlog feature (sub-feats of feat-009)
  to ship once needed. The spec explicitly says "OTel is the
  wire format" — vendors that ingest OTel get coverage today
  without a dedicated module.

## Proposed chunks (7 total)

1. **Hook fan-out + error isolation + on_step wiring.** Internal
   list-of-hooks normalisation; fire on_step per step appended;
   async-hook awaiting; per-hook try/except with WARN logging.
   Constructor accepts `StepHook | list[StepHook]` and
   `FinishHook | list[FinishHook]`. Unit tests: single hook, list
   of hooks, async hook, sync hook, failing hook doesn't crash
   run + logs WARN, ordering preserved.

2. **JSON log format option.** `JsonFormatter` in core; config
   surface (`logging.format: "json" | "text"`); applied alongside
   `RunIdFilter`. Defaults to "text". Unit tests: text fallback,
   json output includes run_id + standard fields, extra fields
   passed through.

3. **`agentforge` adds `opentelemetry-api` dependency** + helper
   `agentforge_core/observability/tracing.py` providing a
   `get_tracer()` shim. Framework-level span emission (no
   exporter — spans are no-ops until a tracer provider is set).
   Instrument `Agent.run`, strategy.iteration calls, tool dispatch
   (in `StrategyBase._dispatch_tool`), and the evaluator loop.
   Unit tests: spans emitted with correct names + attributes when
   a test tracer provider is installed.

4. **`agentforge-otel` package skeleton + tracer setup.** New
   workspace member with pyproject.toml; `OpenTelemetryHook` with
   `__init__(endpoint=, service_name=, sample_rate=,
   redact_fields=)`. Initialises the global tracer provider on
   first hook construction. Tests: hook constructs without
   network; tracer provider gets set; idempotent re-init.

5. **`OpenTelemetryHook` implements step + finish hook contracts.**
   The hook's `__call__` dispatches on type; step events add
   attributes to the current span (token usage, cost, tool name);
   finish events close the root span and add summary attributes.
   Argument-field redaction. Tests: span attributes + redaction.

6. **End-to-end span tree.** Wire the tracer provider into the
   framework's instrumentation points so that constructing an
   `OpenTelemetryHook` produces the full span tree (`agent.run` →
   `strategy.iteration` → `llm.call` → `tool.call` →
   `evaluator.<name>`). In-memory OTLP exporter for tests asserts
   the tree shape.

7. **Docs + PR.** Implementation status + Runbook + CHANGELOG +
   roadmap + forward-ref sweep + raise PR.

## TODO

- [x] User approves scope (single PR, Option B).
- [ ] Chunks 1-7 implementation.
- [ ] PR.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/features/feat-009-observability.md`
