# 14 — Deploy your agent

> **Goal:** get the agent running somewhere durable (container,
> serverless, batch job) with proper secrets and observability.
> **Time:** ~30 minutes.
> **Prereqs:** runbooks 01, 08, 12.

## TL;DR

```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY agentforge.yaml ./
RUN uv sync --frozen
ENV AGENTFORGE_ENV=prod
CMD ["uv", "run", "agentforge", "run", "--task-file", "/in/task.txt", "--output-format", "json"]
```

## Step by step

1. **Pin every dependency.** `uv.lock` must ship with the
   image. `uv sync --frozen` enforces that.
2. **Use environment overlays.** Ship `agentforge.yaml` +
   `agentforge.prod.yaml`; set `AGENTFORGE_ENV=prod` in the
   container. The framework merges the overlay automatically.
3. **Mount secrets via env.** `${AWS_ACCESS_KEY_ID}` etc. in
   the YAML resolve from the container's env. Never bake
   secrets into the image.
4. **Provision the memory store.** If using Postgres, run
   `agentforge db migrate` as a pre-deploy step (helm hook,
   k8s Job, deployment script).
5. **Configure observability** — export `OTEL_EXPORTER_OTLP_
   ENDPOINT`, `OTEL_RESOURCE_ATTRIBUTES=service.name=...`.
6. **Health probe.** `agentforge health --output-format json`
   exits 0 when config + modules + backends are all OK; perfect
   for k8s readiness probes.

## Variations

- **Serverless.** Same image, different entrypoint. Lambda /
  Cloud Run trigger calls `agentforge run` with the task from
  the event.
- **Batch worker.** Loop over a queue; reuse the Agent across
  tasks. `Agent` is thread-safe; each `run` creates fresh
  per-run state.
- **Multi-tenant.** One Agent per tenant; route requests by
  `project` / `agent` claim namespace.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Container exits 2 on start | config invalid in the prod overlay | check `agentforge config validate --env prod` locally |
| `connection refused` on DB | network policy blocking | mount the secret AND open egress |
| OTel spans not appearing | service.name not set | export `OTEL_RESOURCE_ATTRIBUTES=service.name=<your-agent>` |
| Probe fails intermittently | cold-start LLM auth | bump probe initial delay; cache provider client across requests |

## Related

- Runbook 08 — Add memory (DSN secrets, migration)
- Runbook 12 — Add observability
- Runbook 15 — Upgrade your agent (release process)

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
