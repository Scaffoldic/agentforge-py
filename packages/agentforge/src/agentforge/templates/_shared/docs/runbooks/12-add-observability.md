# 12 — Add observability

> **Goal:** stream structured logs + distributed traces from
> every agent run to your APM stack.
> **Time:** ~15 minutes.
> **Prereqs:** runbook 01.

## TL;DR

```yaml
# agentforge.yaml
logging:
  format: json
  run_id_filter: true
modules:
  observability:
    - name: otel
      config:
        endpoint: "${OTEL_EXPORTER_OTLP_ENDPOINT}"
        service_name: "{{ project_slug }}"
```

```bash
agentforge add module otel
```

## Step by step

1. **Turn on JSON logging.** `logging.format: json` swaps the
   default text formatter for `JSONFormatter`; every log line
   becomes one JSON object suitable for piping into a log
   aggregator.
2. **Enable run_id propagation.** `run_id_filter: true`
   installs a logging filter that attaches the active run's
   `run_id` to every record under that run's context. Cross-
   reference runs across components.
3. **Install OTel.** `agentforge add module otel` adds
   `agentforge-otel`; the framework's root span (`agent.run`)
   then becomes the parent of every strategy / LLM / tool span.
4. **Point at your collector.** OTLP/gRPC by default; set
   `OTEL_EXPORTER_OTLP_ENDPOINT` (or hard-code in the YAML).
   Service name = project slug by default.
5. **Custom hooks.** Implement `on_step(step)` / `on_finish(
   result)` callables and pass them to `Agent(on_step=...,
   on_finish=...)` for bespoke metrics; multiple hooks fan out
   in parallel.

## Variations

- **Custom log channels.** Audit decisions go to
  `agentforge.audit`; route them to a security store separately
  from app logs.
- **Vendor backends** — Langfuse / Phoenix / Evidently / StatsD
  modules each wrap their own SDK behind the same hook
  contract. Add via `agentforge add module <name>`.
- **Cost dashboards.** `RunResult.cost_usd` + `eval_scores` are
  cheap series for daily cost-vs-quality charts.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No spans in OTel UI | exporter endpoint wrong | check `agentforge config show --resolved` then curl the OTLP endpoint |
| Run id missing from logs | run_id_filter disabled | re-enable in YAML; restart the process |
| Hook breaks the run | exceptions in hooks default to log-and-continue | check the hook's error log; framework isolates failures |
| Spans missing inside strategies | older `agentforge-otel`; iteration spans land in 0.2+ | upgrade the module |

## Related

- Runbook 11 — Add safety guardrails (audit stream)
- Runbook 14 — Deploy your agent
- Feature spec: `docs/features/feat-009-observability.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
