---
feature: feat-014
state: in_progress
branch: feat/014-a2a-protocol
started_at: 2026-05-12
last_milestone_at: 2026-05-12
last_shipped: feat-020 v0.2 scope shipped via PR #26 (merged 2026-05-12)
blocker: null
flags_for_user: []
---

## Active feature

[`feat-014 — A2A protocol`](../../docs/features/feat-014-a2a-protocol.md)

Full-spec scope. 6 chunks:

1. Canonical `AuthPolicy` ABC + `Principal` value in
   `agentforge-core` + A2A exceptions; `EnvBearerAuth` in
   `agentforge`; chat-http refactor.
2. `agentforge-a2a` package skeleton + value types
   (`A2AResponse`, peer/expose config) + `A2AClientRunner` /
   `A2AServerRunner` Protocols.
3. `agent_call(target, payload)` client + `BearerAuth` /
   `MutualTLSAuth` + `FakeA2AClientRunner` for tests.
4. `A2AServer` FastAPI app + bearer auth + parent_run_id
   propagation + budget cap; `A2ABridge.from_config`.
5. `A2AConfig` Pydantic schema + module-schemas validation hook.
6. Docs (spec §10/§11) + roadmap + CHANGELOG + state + PR.

## Last shipped

[`feat-020 — Chat agents (v0.2 scope)`](../../docs/features/feat-020-chat-agents.md)
opened as PR #26 across three packages:

- **`agentforge-core` extensions**: `ChatHistoryStore` and
  `HistoryTruncationStrategy` ABCs; `ChatTurn`, `SessionInfo`,
  `ChatChunk`, `ChatResponse` frozen value models;
  `run_chat_history_conformance` / `run_truncation_conformance`
  harnesses; `modules.chat:` schema (`ChatConfig` /
  `ChatHistoryDriverConfig` / `ChatTruncationConfig` /
  `ChatSessionConfig`) + `_validate_driver` helper.
- **`agentforge-chat` (new)**: `ChatSession` (send + stream +
  history + reset + idempotency + per-turn/per-session budgets +
  input/output guardrails); `InMemoryChatHistory` +
  `SqliteChatHistory` drivers; four truncation strategies
  (sliding-window / token-budget / summarise-oldest / hybrid);
  per-session lock registry + LRU+TTL idempotency cache;
  `build_chat_session_from_config(config, agent)`.
- **`agentforge-chat-http` (new)**: FastAPI `ChatServer` with
  REST + WebSocket + SSE + bearer-auth + token-bucket rate
  limiting + cross-owner 403; `BearerAuthPolicy` ABC +
  `EnvBearerAuth` placeholder pending feat-014.

Deviations recorded in spec §11:

- Streaming is buffer-then-stream only (strategy ABC has no
  `stream()` method yet; sentence-segmented chunks ship the
  correct wire format today).
- Cancellation is pre-LLM only (WS disconnect propagates).
- Single-process locking only (cross-process Redis lock is
  v0.3).
- `BearerAuthPolicy` is a v0.2 stub; becomes a thin adapter
  on top of feat-014's `AuthPolicy` when that lands.
- Approximate token counting in `TokenBudget`.

Deferred to v0.3 follow-up PRs:

- `agentforge-chat-history-postgres` driver.
- `agentforge-chat-history-redis` driver.
- `agentforge-chat-slack` reference channel adapter.
- Real per-token streaming through the strategy loop.
- Cross-process per-session locking.
- Provider-aware tokenisation.
- TS port.

### Previously

[`feat-015 — Pipeline & deterministic tasks`](../../docs/features/feat-015-pipeline-and-tasks.md)
shipped in PR #25 (merged 2026-05-12).

## Next pick candidates (canonical numbering)

- **feat-014** — A2A (agent-to-agent) protocol. v0.4-target.
- **feat-020 v0.3 follow-ups** — postgres / redis / slack
  drivers, real streaming, cross-process lock, provider-aware
  tokeniser.
- Vendor observability sub-feats (langfuse/phoenix/evidently/
  statsd).
- Backfill chore PRs (Runbooks for feat-001–005).

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
