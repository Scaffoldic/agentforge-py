---
feature: feat-009 v0.2 follow-up — vendor backends
state: in_review
branch: chore/feat-009-vendor-backends-langfuse-phoenix-evidently-statsd
started_at: 2026-05-13
last_milestone_at: 2026-05-13
last_shipped: feat-014 v0.3 — A2A per-token streaming + unified StreamingChunkKind shipped via PR #35 (merged 2026-05-13)
blocker: null
flags_for_user: []
---

## Active feature

[`feat-009 — Observability`](../../docs/features/feat-009-observability.md)
v0.2 follow-up: closes the four vendor backends spec §4.4
left for v0.2 in one PR per user-chosen "All four backends
in one PR" scope.

- **`agentforge-langfuse`** — Langfuse trace dashboard.
- **`agentforge-phoenix`** — Arize Phoenix dashboard.
- **`agentforge-evidently`** — Evidently agent metrics + drift.
- **`agentforge-statsd`** — StatsD UDP metrics emitter.

Each follows the runner-Protocol pattern; SDK is an optional
extra; unit tests inject fake runners; live tests scoped to
developer machines (no CI services for these vendors).

## Last shipped

[`feat-014 v0.3`](../../docs/features/feat-014-a2a-protocol.md)
shipped via PR #35 (merged 2026-05-13). Closes the two
remaining v0.2-deferred items: per-token A2A streaming via
`Agent.stream(task)` and unified `StreamingChunkKind`. The
per-run hook kwarg on `Agent.run` was obviated by the
streaming refactor and dropped from scope.

### Previously

- feat-020 v0.2 — postgres + redis history + slack adapter +
  per-token streaming foundation (PR #34, 2026-05-13).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33, 2026-05-12).
- feat-013 v0.2 — production MCP runner (PR #32).

## Next pick candidates

We're mid-v0.2.0 cycle. Sequence continues v0.3 → v0.4 → 1.0
per [ADR-0015](../../docs/adr/0015-coordinated-release-train.md).

**Remaining backlog:**

- **Sub-feat backlog** (no canonical numbers yet) — GraphRAG
  hybrid retrieval, BM25 + vector hybrid search, `Reranker`
  ABC, schema migrations.
- **Strategy-level streaming overrides** — concrete
  `ReasoningStrategy.stream` impls on `ReActLoop` etc. (now
  that the contract is locked across chat + A2A).
- **feat-009 v0.3 polish** — child OTel spans, A2A trace
  propagation, content-based redaction.

**Already shipped on the v0.1 → v0.2 line:**

- feat-013 v0.2 — production MCP runner (PR #32).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33).
- feat-020 v0.2 — chat history + adapters + streaming (PR #34).
- feat-014 v0.3 — A2A per-token streaming + unified
  `StreamingChunkKind` (PR #35).
- feat-009 v0.2 — vendor backends (in review).

After v0.2.0 lands, v0.3.0 is reserved for the next round of
community / ecosystem feedback. v0.4.0 brings TypeScript to
parity with the Python v0.2 surface per
[ADR-0002](../../docs/adr/0002-multi-language-python-typescript.md).

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
