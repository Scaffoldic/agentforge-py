---
feature: none
state: in_progress
branch: chore/reconcile-spec-status-drift
started_at: 2026-05-12
last_milestone_at: 2026-05-12
last_shipped: feat-014 shipped via PR #27 (merged 2026-05-12)
blocker: null
flags_for_user: []
---

## Active feature

*None — awaiting next pick.*

## Last shipped

[`feat-014 — A2A protocol`](../../docs/features/feat-014-a2a-protocol.md)
opened as PR #27. Two halves shipped together:

- **Canonical auth refactor** in `agentforge-core`:
  - `agentforge_core.contracts.auth.AuthPolicy` ABC.
  - `agentforge_core.values.auth.Principal` frozen dataclass.
  - `A2ACallError` / `A2AAuthError` / `A2ATimeout` exceptions.
  - `agentforge.auth.EnvBearerAuth` concrete impl;
    `chat-http` `BearerAuthPolicy` aliased to the canonical
    contract.
- **New `agentforge-a2a` package**:
  - `agent_call(target, payload, *, peers, timeout_s,
    budget_usd, budget)` outgoing client.
  - `A2APeer.from_config(...)` + bearer + mTLS credentials.
  - `A2AServer(agent, *, auth, endpoints)` FastAPI app with
    `POST /a2a/v1/calls` + `GET /a2a/v1/info`, run_id chain
    via `X-AgentForge-Run-Id`, optional budget cap via
    `X-AgentForge-Budget-Usd`.
  - `A2ABridge.from_config(config, ...)` orchestrator with
    `start()` / `close()` lifecycle.
  - `A2AConfig` Pydantic schema; `A2ABridge.config_schema =
    A2AConfig`.
  - Production transport runners scaffolded with
    `# pragma: no cover` (mirrors feat-013 MCP).
  - Entry point `agentforge.protocols.a2a`; `manifest.yaml`
    for `agentforge add module a2a`.

Deviations recorded in spec §10:

- Production HTTP runner pending live integration tests.
- FastAPI used (matches chat-http precedent) instead of bare
  Starlette as spec §4.4 hinted.
- Outgoing auth is dict-driven (no policy abstraction);
  server-side bearer is via the canonical `AuthPolicy`.
- A2A discovery, bi-directional streaming, TS port deferred.

### Previously

[`feat-020 — Chat agents (v0.2 scope)`](../../docs/features/feat-020-chat-agents.md)
shipped in PR #26 (merged 2026-05-12).

## Next pick candidates (canonical numbering)

- **feat-014 v0.4.1 follow-ups** — production HTTP runner
  against a real A2A peer; A2A discovery / registry;
  bi-directional streaming.
- **feat-020 v0.3 follow-ups** — postgres / redis / slack
  drivers, real per-token streaming, cross-process locking,
  provider-aware tokeniser.
- Vendor observability sub-feats
  (langfuse/phoenix/evidently/statsd).
- Backfill chore PRs (Runbooks for feat-001–005).

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
