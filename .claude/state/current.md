---
feature: feat-014 v0.3 follow-up
state: in_review
branch: chore/feat-014-v0.3-a2a-per-token-streaming-chunk-kind-unification
started_at: 2026-05-13
last_milestone_at: 2026-05-13
last_shipped: feat-020 v0.2 follow-up shipped via PR #34 (merged 2026-05-13) — postgres + redis chat-history + slack adapter + ReasoningStrategy.stream() + RedisSessionLock + provider-aware tokeniser
blocker: null
flags_for_user: []
---

## Active feature

[`feat-014 — A2A protocol`](../../docs/features/feat-014-a2a-protocol.md)
v0.3 follow-up: closes the two remaining v0.2-deferred items
(per-token A2A streaming + chunk-kind unification) in one PR
per user-chosen "Full v0.3 bundle" scope. The per-run hook
kwarg on `Agent.run` was **obviated** by the streaming
refactor (no remaining caller) and dropped from scope.

## Last shipped

[`feat-020 — Chat agents (v0.2 follow-up)`](../../docs/features/feat-020-chat-agents.md)
shipped via PR #34 (merged 2026-05-13). Closes the six items
v0.1 deferred in one bundle:

- **`agentforge-chat-history-postgres`** — asyncpg-backed
  driver with dual-table schema + composite index +
  TTL/encryption_at_rest/full_text_search capabilities.
- **`agentforge-chat-history-redis`** — redis-py async-backed
  driver with native TTL + sorted-set turn indexing.
- **`agentforge-chat-slack`** — Slack reference adapter
  batching `chat.update` calls every `batch_window_s` seconds.
- **Per-token streaming foundation** —
  `ReasoningStrategy.stream()` non-abstract default +
  `Agent.stream(task)` async iterator + `StreamingEvent`
  value type + `ChatSession._stream_per_token` graduation.
  Now unblocking feat-014 v0.3 (active above).
- **Cross-process locking** — `SessionLock` Protocol +
  `RedisSessionLock` with `SET NX PX` + UUID fencing + Lua
  unlock.
- **Provider-aware tokeniser** — `tiktoken_tokeniser` +
  `anthropic_tokeniser` + `TokenBudget(tokeniser=...)`.

### Previously

- feat-013 v0.2 — production MCP runner (PR #32).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33).

## Next pick candidates

We're mid-v0.2.0 cycle. Sequence continues v0.3 → v0.4 → 1.0
per [ADR-0015](../../docs/adr/0015-coordinated-release-train.md).

**Remaining backlog:**

- **feat-009 vendor backends** — `agentforge-langfuse`,
  `-phoenix`, `-evidently`, `-statsd`.
- **Sub-feat backlog** (no canonical numbers yet) — GraphRAG
  hybrid retrieval, BM25 + vector hybrid search, `Reranker`
  ABC, schema migrations.
- **Strategy-level streaming overrides** — concrete
  `ReasoningStrategy.stream` impls on `ReActLoop` etc. (now
  that the contract is locked across chat + A2A).

**Already shipped on the v0.1 → v0.2 line:**

- feat-013 v0.2 — production MCP runner (PR #32).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33).
- feat-020 v0.2 — postgres + redis history + slack adapter +
  streaming + cross-process lock + tokeniser (PR #34).
- feat-014 v0.3 — A2A per-token streaming + unified
  `StreamingChunkKind` (in review).

After v0.2.0 lands, v0.3.0 is reserved for the next round of
community / ecosystem feedback. v0.4.0 brings TypeScript to
parity with the Python v0.2 surface per
[ADR-0002](../../docs/adr/0002-multi-language-python-typescript.md).

Spec `Target version` metadata is aspirational and predates
any release. When a feature lands earlier or later than its
declared target, the tag wins.

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
