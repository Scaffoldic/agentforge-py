---
feature: feat-024 — Schema migrations framework
state: in_review
branch: feat/024-schema-migrations
started_at: 2026-05-14
last_milestone_at: 2026-05-14
last_shipped: feat-023 — GraphRAG hybrid retrieval shipped via PR #44 (merged 2026-05-14)
blocker: null
flags_for_user: []
---

## Active feature

Bundled feat-024 PR per user-chosen "Spec + framework +
all four drivers" scope. Closes the last un-numbered v0.2
persistence sub-feat from `docs/roadmap.md`.

- New canonical spec at
  `docs/features/feat-024-schema-migrations.md`.
- `Migration` Pydantic value + `MigrationStatus` +
  `Migrator` Protocol +
  `MigrationChecksumError` at
  `agentforge_core/contracts/migrator.py`.
- `discover_migrations(path, *, suffix)` helper at
  `agentforge_core/migrations/discover.py`.
- Per-driver migrators:
  - `PostgresMigrator` + 2 migration files
  - `SqliteMigrator` + 3 migration files (incl. feat-022
    FTS5 as `0002`)
  - `Neo4jMigrator` + 2 Cypher migration files
  - `SurrealMigrator` + 2 SurrealQL migration files
- `agentforge db migrate` + `agentforge db migrate-status`
  CLI subcommands.
- All four drivers' `init_schema()` continues to work,
  now delegating to the migration framework.

## Last shipped

feat-023 — GraphRAG hybrid retrieval shipped via PR #44
(merged 2026-05-14).

### Previously

- feat-022 v0.2 follow-up — native hybrid for Postgres +
  SQLite (PR #43).
- feat-022 — BM25 + vector hybrid search (PR #42).
- feat-002 + feat-009 v0.3.x strategy follow-ups bundle
  (PR #41).
- feat-002 + feat-009 v0.3 polish + feat-021 follow-up
  bundle (PR #40).
- feat-021 vendor reranker sister packages (PR #39).
- feat-021 v0.2 follow-up — `retrieval:` YAML block +
  builder (PR #38).
- feat-021 — Reranker ABC + Retriever integration
  (PR #37).
- feat-009 v0.2 — vendor observability backends (PR #36).
- feat-014 v0.3 — A2A per-token streaming (PR #35).
- feat-020 v0.2 — postgres + redis history + slack +
  streaming (PR #34).

## Next pick candidates

Remaining v0.2 backlog (sister-package follow-ups + v0.3+
items):

- **Native `lexical_search` on Neo4j / SurrealDB**
  (feat-022 sister-package follow-up).
- **Native single-query graph-augmented retrieval inside
  Neo4j / SurrealDB** (feat-023 sister-package follow-up).
- **Parameterized migrations** for Postgres `vector(N)` +
  SurrealDB `HNSW DIMENSION N` (feat-024 v0.3+ open
  item).
- **`down` migrations / schema rollback** (feat-024 v0.3+).
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
- feat-024 — Schema migrations framework (in review).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
