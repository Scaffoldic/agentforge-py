# Roadmap

What's planned but not yet shipped. Each entry is a
"feature-in-flight" with a rough scope; the full design lands in a PR
when work begins. Items are listed by feature number, not priority —
order may shift based on user demand.

## In flight

### feat-008 — `agentforge-memory-postgres` (production persistence)

Production-grade `MemoryStore` and `VectorStore` over Postgres via
`asyncpg` and the [`pgvector`](https://github.com/pgvector/pgvector)
extension. Sister package to `agentforge-memory-sqlite`; same locked
contracts, same conformance suites — drop-in replacement for
deployments that need scale, multi-writer concurrency, or
managed-database guarantees (RDS, Neon, Supabase, etc.).

Deferred from feat-007 because SQLite already covers single-host
v0.1 use cases and Postgres deserves real load testing rather than
being rushed in alongside the contract work.

**Scope:**
- New workspace member `packages/agentforge-memory-postgres/`.
- `PostgresMemoryStore` (claims) + `PostgresVectorStore` (vectors via
  `CREATE EXTENSION vector;`). Both pass `run_memory_conformance` and
  `run_vector_conformance` verbatim.
- Schema migrations: opt-in `await store.init_schema()` (idempotent
  `CREATE TABLE IF NOT EXISTS`); no migration framework yet — that
  lands when we have a v0.1.0 → v0.2.0 schema delta.
- Live integration tests gated on `RUN_LIVE_POSTGRES=1` +
  `POSTGRES_URL=…`. Local docker-compose for development.
- Pricing entry-point registration (`embeddings.postgres` reserved if
  pgvector hosts embeddings server-side via `vector_l2_ops`-aware
  search; otherwise pure persistence).

**Estimated chunks:** 4 — package skeleton + claims, vector store,
live integration test fixture, CHANGELOG/PR.

---

## Backlog (no design yet)

These are tracked here so they don't get lost. Designs land when
they get prioritised:

- **feat-004 — Anthropic SDK direct provider.** First-party Anthropic
  client (not via Bedrock). Mirrors the locked `LLMClient` surface
  feat-003 exercises.
- **feat-005 — OpenAI / Azure provider.** Same shape as feat-004.
- **feat-006 — `agentforge-eval-geval`.** Cheap-judge model + eval
  framework. Closes the `scorer="judge"` placeholder from feat-002's
  `TreeOfThoughts`.
- **feat-010 — Entry-point auto-loader.** `pip install agentforge-X`
  alone enables `Agent(model="X:...")` without an explicit import.
- **GraphRAG-style hybrid retrieval** (post-feat-009). Combines vector
  retrieval with graph expansion — pull the top-k vector matches,
  then traverse outgoing edges to enrich context.
- **Hybrid search** (BM25 + vector fusion) inside the locked
  `VectorStore` capability vocabulary.
- **Reranker contract** — `Reranker` ABC for cross-encoder reranking
  on top of `VectorStore.search`.
- **Schema migrations** for persistent stores (Postgres, SQLite). Lands
  alongside the first breaking schema delta.
