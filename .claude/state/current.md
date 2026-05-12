---
feature: feat-015
state: in_progress
branch: feat/015-pipeline-and-tasks
started_at: 2026-05-12
last_milestone_at: 2026-05-12
last_shipped: feat-013 shipped via PR #24 (merged 2026-05-12)
blocker: null
flags_for_user: []
---

## Active feature

[`feat-015 — Pipeline & deterministic tasks`](../../docs/features/feat-015-pipeline-and-tasks.md)

Full-spec scope. 6 chunks:

1. `Task` ABC + `PipelineResult` value + conformance harness.
2. `Pipeline` engine + DAG + parallelism + `PipelineFailure`.
3. `pipeline_findings` built-in tool + `Agent(pipeline=...)`
   integration + recording/replay.
4. Config schema (`modules.pipeline:`) + module validation +
   `build_agent_from_config` wiring.
5. Public API re-exports + renderer-compat sanity test.
6. Docs (spec §10/§11) + roadmap + CHANGELOG + state + PR.

## Last shipped

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
