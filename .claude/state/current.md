---
feature: feat-023 — GraphRAG hybrid retrieval
state: in_review
branch: feat/023-graphrag-hybrid-retrieval
started_at: 2026-05-14
last_milestone_at: 2026-05-14
last_shipped: feat-022 v0.2 follow-up — native hybrid for Postgres + SQLite shipped via PR #43 (merged 2026-05-14)
blocker: null
flags_for_user: []
---

## Active feature

Bundled feat-023 PR per user-chosen "Full spec in one PR"
scope. Closes the second of the three un-numbered v0.2
retrieval sub-feats from `docs/roadmap.md`.

- New canonical spec at
  `docs/features/feat-023-graphrag-hybrid.md`.
- `GraphExpansion` Pydantic value type at
  `agentforge_core/values/retrieval.py` bundling
  `store` + `max_hops` + `edge_types` + `text_property` +
  `decay`.
- `Retriever(graph_expansion=...)` constructor kwarg.
  Composes orthogonally with `mode="vector"` /
  `mode="hybrid"` and optional `Reranker`. Pipeline:
  `(base retrieve) → (graph expand) → (rerank)`.
- `RetrievalConfig.graph_expansion` +
  `GraphExpansionConfig` schema block;
  `build_retriever_from_config` wires the graph store
  under the existing `graph_stores` entry-point category.
- Missing-graph-node tolerance + DEBUG logging.

## Last shipped

feat-022 v0.2 follow-up — native hybrid for Postgres +
SQLite shipped via PR #43 (merged 2026-05-14).

### Previously

- feat-022 — BM25 + vector hybrid search (PR #42).
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
- feat-020 v0.2 — postgres + redis history + slack
  adapter + per-token streaming foundation (PR #34).

## Next pick candidates

Remaining v0.2 backlog:

- **Schema migrations framework** for persistent stores
  (un-numbered).
- **Native `lexical_search` on Neo4j / SurrealDB**
  (sister-package follow-up to feat-022; deferred until
  requested).
- **Native single-query graph-augmented retrieval inside
  Neo4j / SurrealDB** (single Cypher / SurrealQL query
  combining vector + graph; sister-package follow-up to
  feat-023).
- **Evidently real-time drift dashboards via Cloud**
  (feat-009 v0.3+ open item).
- **Multi-cluster Redlock for `RedisSessionLock`** and
  **sentence-window streaming output guardrails**
  (feat-020 v0.3+ open items).

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
  SQLite (PR #43).
- feat-023 — GraphRAG hybrid retrieval (in review).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
