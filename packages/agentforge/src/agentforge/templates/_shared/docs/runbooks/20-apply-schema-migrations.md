# 20 — Apply schema migrations

> **Goal:** evolve a persistent store's schema (Postgres /
> SQLite / Neo4j / SurrealDB) without losing data or
> hand-running SQL on production.
> **Time:** ~10 minutes for the first migration.
> **Prereqs:** runbook 08 (a persistent store wired in).

## TL;DR

```bash
# 1. Generate a migration file from the template.
agentforge db migrate new "add_user_role_column"

# 2. Edit the generated migration:
# .agentforge/migrations/postgres/20260514T101200__add_user_role_column.sql
# Add your DDL/DML under -- up

# 3. Apply pending migrations.
agentforge db migrate up

# 4. Confirm.
agentforge db migrate status
```

## Step by step

1. **Pick the target store.** Migrations are per-driver. The
   v0.2 framework ships:
   - Postgres (`.agentforge/migrations/postgres/*.sql`)
   - SQLite (`.agentforge/migrations/sqlite/*.sql`)
   - Neo4j (`.agentforge/migrations/neo4j/*.cypher`)
   - SurrealDB (`.agentforge/migrations/surrealdb/*.surql`)
2. **Generate a migration.** `agentforge db migrate new
   "<description>"` writes a timestamped file under the
   appropriate driver directory.
3. **Author the `-- up` block.** Use idempotent DDL where you
   can (`CREATE INDEX IF NOT EXISTS ...`); the migrator tracks
   applied state in a `__agentforge_migrations` table.
4. **Parameterise dimension-sensitive schemas.** Postgres
   `vector(N)` and SurrealDB `HNSW DIMENSION N` should use
   `${VECTOR_DIM}` so the same migration adapts to
   3-small (1536) vs 3-large (3072) without forking:

   ```sql
   -- up
   CREATE TABLE docs (
     id text primary key,
     text text,
     embedding vector(${VECTOR_DIM})
   );
   ```

   Set `${VECTOR_DIM}` via `agentforge db migrate up
   --var VECTOR_DIM=1536` or in `agentforge.yaml`
   under `db.migrations.variables`.
5. **Run `up`.** `agentforge db migrate up` applies every
   pending migration in timestamp order, in a transaction
   per file (where the driver supports it).
6. **Verify with `status`.** `agentforge db migrate status`
   prints applied + pending counts.

## Variations

- **CI gate.** Add `agentforge db migrate status
  --fail-on-pending` to your deploy pipeline to refuse a
  rollout if migrations are unapplied.
- **Multiple stores.** Run `migrate up` per-store; the CLI
  detects available drivers via your config.
- **`init_schema` shim** — pre-v0.2 agents that called
  `MemoryStore.init_schema()` still work; you can opt-out by
  setting `db.init_schema: false` and switching to migrations.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `MigrationConflict` | two devs added migrations with the same timestamp | regenerate one to bump the timestamp |
| Migration applied but data missing | non-idempotent up that crashed mid-flight | manually fix; record entry in `__agentforge_migrations` |
| `${VAR} not substituted` | variable not declared | pass `--var VAR=value` or add to `db.migrations.variables` |
| Dim mismatch on `vector(N)` | upgrading embedding model | new migration that recreates the column with the new dim |

## Related

- Runbook 08 — Add memory + retrieval
- Runbook 18 — Add hybrid search
- Feature spec: `docs/features/feat-024-schema-migrations.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
