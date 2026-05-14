---
feature: feat-024 v0.3 polish — parameterized migrations (Postgres + SurrealDB vectors)
state: in_review
branch: feat/024-parameterized-migrations-vectors
started_at: 2026-05-14
last_milestone_at: 2026-05-14
last_shipped: feat-024 — Schema migrations framework shipped via PR #45 (merged 2026-05-14)
blocker: null
flags_for_user: []
---

## Active feature

Bundled feat-024 v0.3 polish PR per user-chosen "Full
bundle: core + Postgres + SurrealDB" scope. Closes the
deferred dim-parameterized item from PR #45.

- `render_migration_up(body, variables)` helper at
  `agentforge_core.migrations.template` —
  `${var}` substitution via Python's `string.Template`
  with `safe_substitute` semantics.
- All four per-driver migrators
  (`PostgresMigrator` / `SqliteMigrator` /
  `Neo4jMigrator` / `SurrealMigrator`) gain an optional
  `variables=` kwarg.
- Postgres + SurrealDB get per-store migration
  subdirectories. Vector migrations move to
  `migrations/vector/0100_vectors.{sql,surql}` (id
  range 0100-0199 to avoid colliding with memory's
  0001 in the shared tracking table).
- `PostgresVectorStore.migrator()` and
  `SurrealVectorStore.migrator()` pre-configure with
  `variables={"dimensions": str(self._dim)}` + the
  vector subdir path.
- `_build_init_schema_sql` / `_build_init_schema`
  helpers removed; `init_schema()` on both vector
  stores delegates to the migration framework.

## Last shipped

feat-024 — Schema migrations framework shipped via
PR #45 (merged 2026-05-14).

### Previously

- feat-023 — GraphRAG hybrid retrieval (PR #44).
- feat-022 v0.2 follow-up — native hybrid for Postgres +
  SQLite (PR #43).
- feat-022 — BM25 + vector hybrid search (PR #42).
- feat-002 + feat-009 v0.3.x strategy follow-ups bundle
  (PR #41).
- feat-002 + feat-009 v0.3 polish + feat-021 follow-up
  bundle (PR #40).
- feat-021 vendor reranker sister packages (PR #39).
- feat-021 v0.2 follow-up — `retrieval:` YAML block
  + builder (PR #38).
- feat-021 — Reranker ABC + Retriever integration
  (PR #37).
- feat-009 v0.2 — vendor observability backends (PR #36).
- feat-014 v0.3 — A2A per-token streaming (PR #35).
- feat-020 v0.2 — postgres + redis history + slack +
  streaming (PR #34).

## Next pick candidates

Remaining backlog (sister-package follow-ups + v0.3+
polish):

- **Native `lexical_search` on Neo4j / SurrealDB**
  (feat-022 sister-package follow-up).
- **Native single-query graph-augmented retrieval inside
  Neo4j / SurrealDB** (feat-023 sister-package
  follow-up).
- **`down` migrations / schema rollback** (feat-024
  v0.3+).
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
- feat-022 v0.2 follow-up — native hybrid for Postgres +
  SQLite (PR #43).
- feat-023 — GraphRAG hybrid retrieval (PR #44).
- feat-024 — Schema migrations framework (PR #45).
- feat-024 v0.3 polish — parameterized migrations
  (in review).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
