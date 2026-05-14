---
feature: feat-025 — Neo4jVectorStore + SurrealDB native lexical_search
state: in_review
branch: feat/025-neo4j-vector-store-plus-surrealdb-lexical
started_at: 2026-05-14
last_milestone_at: 2026-05-14
last_shipped: feat-024 v0.3 polish — parameterized migrations shipped via PR #46 (merged 2026-05-14)
blocker: null
flags_for_user: []
---

## Active feature

Bundled PR per user-chosen "Both in one PR" scope. Closes
two adjacent retrieval-completeness gaps:

1. **feat-025** — `agentforge-memory-neo4j` lacked a
   `VectorStore`. New `Neo4jVectorStore` uses Neo4j 5.13+
   native `CREATE VECTOR INDEX` + `CREATE FULLTEXT INDEX`.
2. **feat-022 follow-up** — SurrealDB was the last
   `VectorStore` without native `lexical_search`. New
   migration adds `DEFINE ANALYZER` + `SEARCH ANALYZER
   ... BM25` index; `SurrealVectorStore.lexical_search`
   queries via `WHERE text @0@ $query` + `search::score`.

After this PR every shipped VectorStore (InMemory /
Postgres / SQLite / SurrealDB / Neo4j) passes both
`run_vector_conformance` and `run_hybrid_search_conformance`.

## Last shipped

feat-024 v0.3 polish — parameterized migrations shipped
via PR #46 (merged 2026-05-14).

### Previously

- feat-024 — Schema migrations framework (PR #45).
- feat-023 — GraphRAG hybrid retrieval (PR #44).
- feat-022 v0.2 follow-up — native hybrid for Postgres
  + SQLite (PR #43).
- feat-022 — BM25 + vector hybrid search (PR #42).
- feat-002 + feat-009 v0.3.x strategy follow-ups bundle
  (PR #41).
- feat-002 + feat-009 v0.3 polish + feat-021 follow-up
  bundle (PR #40).

## Next pick candidates

Remaining backlog (v0.3+ open items + sister-package
follow-ups):

- **`down` migrations / schema rollback** (feat-024
  v0.3+).
- **Native single-query graph-augmented retrieval inside
  Neo4j / SurrealDB** (feat-023 sister-package
  follow-up).
- **Evidently real-time drift dashboards via Cloud**
  (feat-009 v0.3+).
- **Multi-cluster Redlock for `RedisSessionLock`** and
  **sentence-window streaming output guardrails**
  (feat-020 v0.3+).

**Already shipped on the v0.1 → v0.2 line:**

- feat-013 v0.2 — production MCP runner (PR #32).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33).
- feat-020 v0.2 — chat history + adapters + streaming
  (PR #34).
- feat-014 v0.3 — A2A per-token streaming (PR #35).
- feat-009 v0.2 — vendor observability backends (PR #36).
- feat-021 — Reranker ABC + Retriever integration
  (PR #37).
- feat-021 v0.2 follow-up — `retrieval:` YAML block +
  builder (PR #38).
- feat-021 v0.2 follow-up — vendor reranker sister
  packages (PR #39).
- feat-002 + feat-009 v0.3 polish + feat-021 follow-up
  bundle (PR #40).
- feat-002 + feat-009 v0.3.x strategy follow-ups bundle
  (PR #41).
- feat-022 — BM25 + vector hybrid search (PR #42).
- feat-022 v0.2 follow-up — native hybrid for Postgres
  + SQLite (PR #43).
- feat-023 — GraphRAG hybrid retrieval (PR #44).
- feat-024 — Schema migrations framework (PR #45).
- feat-024 v0.3 polish — parameterized migrations
  (PR #46).
- feat-025 — Neo4jVectorStore + SurrealDB native
  lexical_search (in review).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
