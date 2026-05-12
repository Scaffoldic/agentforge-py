---
feature: none
state: in_progress
branch: chore/release-notes-template-and-version-cleanup
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

## Next pick candidates

We haven't tagged anything yet. The next release is **v0.1.0**
— every 0.1-target spec is shipped. After that the natural
minor sequence is v0.2, v0.3, v0.4, 1.0 per
[ADR-0015](../../docs/adr/0015-coordinated-release-train.md).

**Release prep (recommended first):**
- Run [`.claude/checklists/pre-release.md`](../checklists/pre-release.md);
  fill `docs/releases/v0.1.0.md` from
  [`.claude/templates/release-notes.md`](../templates/release-notes.md);
  tag and publish.

**Post-0.1 feature backlog:**
- **feat-014 follow-ups** — production HTTP A2A runner; A2A
  discovery / registry; bi-directional streaming.
- **feat-013 follow-up** — production MCP runner against a real
  server.
- **feat-020 follow-ups** — `agentforge-chat-history-postgres`,
  `-redis`, `-slack` adapter, real per-token streaming,
  cross-process locking, provider-aware tokeniser.
- **Vendor observability sub-feats** —
  `agentforge-langfuse`, `-phoenix`, `-evidently`, `-statsd`.
- **Sub-feat backlog** — GraphRAG hybrid retrieval, BM25 +
  vector hybrid search, `Reranker` ABC, schema migrations.

Spec `Target version` metadata is aspirational and predates any
release. When a feature lands earlier or later than its declared
target, the tag wins.

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
