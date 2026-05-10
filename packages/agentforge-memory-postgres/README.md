# agentforge-memory-postgres

Postgres + [pgvector](https://github.com/pgvector/pgvector)-backed
`MemoryStore` and `VectorStore` for the AgentForge framework.

## What this is

Sister package to `agentforge-memory-sqlite`. Same locked contracts,
same conformance suites — but backed by Postgres with `asyncpg` for
real-world scale, multi-writer concurrency, and managed-database
guarantees (RDS, Neon, Supabase, etc.).

- **`PostgresMemoryStore`** — claim audit log over a single `claims`
  table with composite indices on common filter combinations
  (`project, agent`, `run_id`, `category`).
- **`PostgresVectorStore`** — semantic search over a `vectors` table
  with a pgvector HNSW index (`vector_cosine_ops`). Cosine distance
  is converted to clamped `[0, 1]` similarity at the SQL boundary
  per the locked `VectorStore` contract.

Both pass `agentforge_core.testing.run_memory_conformance` and
`run_vector_conformance` against a real Postgres (gated on
`RUN_LIVE_POSTGRES=1` in CI; always on locally via docker compose).

## Usage

```python
from agentforge_memory_postgres import PostgresMemoryStore, PostgresVectorStore

dsn = "postgresql://postgres:postgres@localhost:5432/agentforge"

async with PostgresMemoryStore.from_dsn(dsn) as memory:
    await memory.init_schema()                # idempotent
    ...

async with PostgresVectorStore.from_dsn(dsn, dimensions=1024) as vectors:
    await vectors.init_schema()               # provisions HNSW index
    ...
```

`init_schema()` is opt-in (idempotent `CREATE TABLE / EXTENSION /
INDEX IF NOT EXISTS`). Skip it for read-only workloads or when the
schema is managed externally; required before first write for full
correctness.

## Local development

```bash
docker compose -f docker-compose.dev.yml up -d
RUN_LIVE_POSTGRES=1 \
  POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/agentforge \
  uv run pytest packages/agentforge-memory-postgres/tests/integration -v
```

The compose file ships `pgvector/pgvector:pg16`, which bundles
Postgres 16 with the pgvector extension preinstalled.

## Capabilities

- **Memory**: `{"transactions"}` — every `put` / `supersede` runs
  inside an asyncpg transaction.
- **Vector**: `{"native_ann"}` is declared **only** after
  `init_schema()` provisions the HNSW index. Without bootstrap the
  driver still works (sequential cosine scan), but it doesn't claim
  ANN — the capability vocabulary is honest per ADR-0009.
