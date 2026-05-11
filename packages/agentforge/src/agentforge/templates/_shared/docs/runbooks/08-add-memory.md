# 08 — Add memory / persistence

> **Goal:** swap the default in-memory store for a durable
> backend (SQLite / Postgres / Neo4j / SurrealDB).
> **Time:** ~10 minutes.
> **Prereqs:** runbook 01.

## TL;DR

```yaml
# agentforge.yaml
modules:
  memory:
    driver: postgres
    config:
      dsn: "${DATABASE_URL}"
      min_size: 1
      max_size: 10
```

```bash
agentforge add module memory-postgres
agentforge db migrate
```

## Step by step

1. **Pick a driver.** Default to SQLite for single-host
   deployments; Postgres for managed-database / multi-writer;
   Neo4j or SurrealDB if you need graph relationships
   (supersede chains, finding lineage).
2. **Install the module.** `agentforge add module memory-<driver>`
   uses the framework's manifest applier (no manual pip).
3. **Configure** under `modules.memory` in `agentforge.yaml`.
   Use `${ENV_VAR}` interpolation for credentials — never put
   them in the YAML literal.
4. **Run schema migration** with `agentforge db migrate`. The
   command is a no-op for drivers that create their schema
   eagerly (in-memory, sqlite); a real DDL pass for postgres /
   neo4j / surrealdb.
5. **Verify** with `agentforge db query 'category:__step'` — if
   your previous runs were recorded, you'll see step claims.

## Variations

- **Drop-in driver swap** — `agentforge swap memory sqlite
  postgres` migrates the configuration; data migration is
  separate (`agentforge db backup` then `db restore`).
- **Multiple categories** — write your own claims via
  `agent.memory.put(Claim(category="custom", ...))`. Reserved
  categories (`__step`, `__eval`, `__run`) belong to the
  framework.
- **TTL** — drivers that declare the `ttl` capability honour
  `agent.memory.set_ttl(...)`. Check with `agent.memory.supports
  ("ttl")`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No module registered for memory:postgres` | driver not installed | `agentforge add module memory-postgres` |
| `connection refused` | DSN points at the wrong host / port | check `${DATABASE_URL}` expansion via `agentforge config show --resolved` |
| `delete() requires at least one filter` | called `memory.delete()` with no args | pass `run_id=` / `category=` / `older_than=` |
| Schema version mismatch on upgrade | driver schema bumped | `agentforge db backup` → `agentforge db migrate` → `agentforge db restore` |

## Related

- Runbook 14 — Deploy your agent (DSN secret management)
- Runbook 15 — Upgrade your agent (schema migrations)
- Feature spec: `docs/features/feat-005-persistence-and-memory.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
