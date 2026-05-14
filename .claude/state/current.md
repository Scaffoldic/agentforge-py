---
feature: feat-002 + feat-009 v0.3.x strategy follow-ups bundle
state: in_review
branch: chore/feat-002-feat-009-strategy-streams-iteration-spans
started_at: 2026-05-14
last_milestone_at: 2026-05-14
last_shipped: feat-002 + feat-009 v0.3 polish + feat-021 follow-up bundle shipped via PR #40 (merged 2026-05-14)
blocker: null
flags_for_user: []
---

## Active feature

Bundled strategy follow-ups PR closing two deferred items
from PR #40 per user-chosen "Strategy follow-ups bundle"
scope:

- **feat-009 v0.3.x** — `strategy.iteration` OTel spans on
  `TreeOfThoughts` + `MultiAgentSupervisor` via extract-method
  refactor (`_iterate_depth`, `_iterate_round`).
- **feat-002 v0.3.x** — `stream()` overrides on
  `PlanExecuteLoop`, `TreeOfThoughts`, and
  `MultiAgentSupervisor`. ReActLoop's override already
  shipped in PR #40; the shared `_events_for_new_steps`
  helper was lifted to `_base.py` for reuse.

## Last shipped

feat-002 + feat-009 v0.3 polish + feat-021 follow-up bundle
shipped via PR #40 (merged 2026-05-14).

### Previously

- feat-021 vendor reranker sister packages (PR #39).
- feat-021 v0.2 follow-up — `retrieval:` YAML block +
  `build_retriever_from_config` (PR #38).
- feat-021 — Reranker ABC + sentence-transformers default
  + Retriever integration (PR #37).
- feat-009 v0.2 — Langfuse + Phoenix + Evidently + StatsD
  vendor observability backends (PR #36).
- feat-014 v0.3 — A2A per-token streaming + unified
  `StreamingChunkKind` (PR #35).
- feat-020 v0.2 — postgres + redis history + slack adapter
  + per-token streaming foundation (PR #34).

## Next pick candidates

Remaining v0.2 backlog:

- **Sub-feat backlog (still un-numbered)** — GraphRAG
  hybrid retrieval, BM25 + vector hybrid search, schema
  migrations.
- **Evidently real-time drift dashboards via Cloud**
  (feat-009 v0.3+ open item).
- **Multi-cluster Redlock for `RedisSessionLock`** and
  **sentence-window streaming output guardrails** (feat-020
  v0.3+ open items).

**Already shipped on the v0.1 → v0.2 line:**

- feat-013 v0.2 — production MCP runner (PR #32).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33).
- feat-020 v0.2 — chat history + adapters + streaming
  (PR #34).
- feat-014 v0.3 — A2A per-token streaming + unified
  `StreamingChunkKind` (PR #35).
- feat-009 v0.2 — vendor observability backends (PR #36).
- feat-021 — Reranker ABC + sentence-transformers default
  + Retriever integration (PR #37).
- feat-021 v0.2 follow-up — `retrieval:` YAML block +
  builder (PR #38).
- feat-021 v0.2 follow-up — vendor reranker sister
  packages (PR #39).
- feat-002 + feat-009 v0.3 polish + feat-021 follow-up
  bundle (PR #40).
- feat-002 + feat-009 v0.3.x strategy follow-ups bundle
  (in review).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
