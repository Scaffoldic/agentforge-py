---
feature: feat-020
state: in_progress
branch: feat/020-chat-agents-v02
started_at: 2026-05-12
last_milestone_at: 2026-05-12
last_shipped: feat-015 shipped via PR #25 (merged 2026-05-12)
blocker: null
flags_for_user: []
---

## Active feature

[`feat-020 — Chat agents`](../../docs/features/feat-020-chat-agents.md)

**v0.2 scope only**: contracts in `agentforge-core`,
`agentforge-chat` package (`ChatSession` + in-memory +
sqlite + 4 truncation strategies), `agentforge-chat-http`
package (FastAPI REST + WS + SSE + bearer auth).

**Deferred to v0.3 follow-ups** (per
`feedback_scope_preferences.md` "one half clearly riskier"
exception): `agentforge-chat-history-postgres`,
`agentforge-chat-history-redis`, `agentforge-chat-slack`,
real per-token streaming, cross-process locking.

6 chunks:

1. Chat contracts + value models + conformance harness.
2. `agentforge-chat` package: drivers + truncation strategies.
3. `ChatSession` (send + stream + idempotency + budgets).
4. `agentforge-chat-http`: FastAPI REST + WS + SSE + bearer auth.
5. `modules.chat:` config schema + `build_chat_session_from_config`.
6. Docs (spec §10/§11) + roadmap + CHANGELOG + state + PR.

## Last shipped

[`feat-015 — Pipeline & deterministic tasks`](../../docs/features/feat-015-pipeline-and-tasks.md)
opened as PR #25 (framework-only feature inside `agentforge`):

- `agentforge_core.contracts.task.Task` ABC +
  `agentforge_core.values.pipeline.PipelineResult` frozen value.
- `agentforge.pipeline.Pipeline` engine with DAG validation
  (cycles / duplicates / missing deps at construction),
  `asyncio.Semaphore`-bounded parallelism, per-task
  `asyncio.wait_for(timeout_s)`, `on_task_error` continue/fail
  modes, `PipelineFailure` exception.
- `PipelineFindingsTool` built-in tool with category/severity
  filters; `Agent(pipeline=...)` kwarg; `Agent.run(task, *,
  context, replay_pipeline)` API; per-run system-prompt
  addendum.
- `modules.pipeline:` config block + `build_pipeline_from_config`
  wired into `build_agent_from_config`.
- `__pipeline` recording category + `load_pipeline_result`
  replay so side-effect-bearing tasks don't double-run on
  `agentforge run --replay`.
- `FinishReason` literal extended with `"pipeline"`.
- Public re-exports + renderer-compat sanity test.

Deviations recorded in spec §10:

- `Agent.run` gained both `context=` and `replay_pipeline=`
  kwargs (spec showed `context=` only).
- `finish_reason = "pipeline"` is new; the CLI maps it to
  generic exit 1 to keep the exit-code surface stable.
- Mid-run pipeline streaming, end-to-end LLM-using task
  example, and TS port are deferred.

### Previously

[`feat-013 — MCP integration`](../../docs/features/feat-013-mcp-integration.md)
shipped in PR #24 as the new Tier-3 `agentforge-mcp` module:

- `MCPClientRunner` / `MCPServerRunner` protocols +
  `MCPToolDescriptor` value.
- `MCPToolAdapter` (`build_adapter(runner, descriptor,
  server_name)`) — synthesises a `Tool` subclass per MCP tool
  with a server-prefixed name + Pydantic input schema.
- `MCPServerClient.{from_stdio, from_http, from_sse}` —
  consumes external MCP servers; `discover_tools` + `tool_filter`.
- `MCPServer.{from_stdio, from_http}` — exposes local tools as
  MCP with `allowed` whitelist semantics.
- `MCPBridge.from_config(config)` — orchestrates clients +
  optional server; `start` / `close` lifecycle.
- `manifest.yaml` so `agentforge add module mcp` registers
  the protocol entry.

Deviations recorded in spec §10:

- Production runner classes (`_SDKClientRunner`,
  `_SDKServerRunner`) scaffolded but scoped to
  `# pragma: no cover` — they raise
  `Production MCP runner not implemented yet` until the
  framework's first integration test against a real MCP server.
- `Agent.tools` auto-merge via `build_agent_from_config` is
  follow-up (today the bridge is opt-in; tests use it via the
  bare constructor).
- TS port deferred.

## Next pick candidates (canonical numbering)

- **feat-015** — Pipelines & deterministic tasks. v0.2-target.
  Runbook 03 cross-references it.
- **feat-014** — A2A (agent-to-agent) protocol. v0.4-target.
- **feat-020** — Chat agents (ChatSession + history stores +
  HTTP/WebSocket/SSE server). v0.2-target. Largest remaining.
- Vendor observability sub-feats (langfuse/phoenix/evidently/
  statsd).

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
