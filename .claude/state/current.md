---
feature: feat-022 v0.2 follow-up — native hybrid for Postgres + SQLite
state: in_review
branch: feat/022-hybrid-postgres-sqlite-native
started_at: 2026-05-14
last_milestone_at: 2026-05-14
last_shipped: feat-022 — BM25 + vector hybrid search shipped via PR #42 (merged 2026-05-14)
blocker: null
flags_for_user: []
---

## Active feature

Bundled feat-022 follow-up PR per user-chosen "Native
hybrid for Postgres + SQLite" scope. Closes the two
sister-package follow-ups feat-022 deferred:

- **`agentforge-memory-postgres`** —
  `embedding_tsv tsvector` generated column + GIN index +
  `lexical_search` via `ts_rank_cd` /
  `plainto_tsquery('english', $1)`. `"hybrid_search"`
  capability declared post-`init_schema()`.
- **`agentforge-memory-sqlite`** — FTS5 virtual table +
  sync triggers + `lexical_search` via `bm25()`.
  `"hybrid_search"` capability always declared.

Both pass `run_hybrid_search_conformance` end-to-end (live
Postgres under `RUN_LIVE_POSTGRES=1`; SQLite via `:memory:`
in CI).

## Last shipped

feat-022 — BM25 + vector hybrid search shipped via PR #42
(merged 2026-05-14).

### Previously

- feat-002 + feat-009 v0.3.x strategy follow-ups bundle
  (PR #41).
- feat-002 + feat-009 v0.3 polish + feat-021 follow-up
  bundle (PR #40).
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

- **GraphRAG-style hybrid retrieval** — vector top-k +
  graph edge traversal (un-numbered, likely feat-023).
- **Schema migrations** for persistent stores (un-numbered).
- **Native `lexical_search` on Neo4j / SurrealDB**
  (sister-package follow-ups to feat-022; deferred until
  requested).
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
  (PR #41).
- feat-022 — BM25 + vector hybrid search (PR #42).
- feat-022 v0.2 follow-up — native hybrid for Postgres +
  SQLite (in review).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
