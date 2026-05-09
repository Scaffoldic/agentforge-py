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

### feat-009 — `GraphStore` ABC + SurrealDB and Neo4j drivers

Adds a third locked contract for graph traversal — the kind of
queries SurrealDB and Neo4j shine on (relationships, paths, multi-hop
reasoning) that don't fit naturally into `MemoryStore` (filter-by-
metadata) or `VectorStore` (cosine similarity).

This unlocks genuinely new agent shapes: knowledge graphs grown over
time, multi-hop reasoning over a corpus, planning across an
ontology. Shoehorning these databases into `MemoryStore` would give
a worse SQLite — keeping `GraphStore` separate respects the contract
layer's purpose (one ABC per concern, not one per backend).

**Scope:**
- **`GraphStore` ABC** in `agentforge-core`:
  - `add_node(id, *, labels, properties)` — idempotent upsert.
  - `add_edge(src, dst, *, type, properties)` — directed.
  - `match(pattern: GraphPattern, *, limit) -> list[GraphMatch]` —
    Cypher-/SurrealQL-flavoured pattern: `(:Doc)-[:CITES]->(:Doc)`.
  - `traverse(start_id, *, edge_types, max_depth) -> list[Path]` —
    breadth-first traversal helper for multi-hop retrieval.
  - `delete_node(id, *, cascade)` and `delete_edge(src, dst, *, type)`.
  - `dimensions()` not applicable — graphs aren't vector-shaped.
  - `capabilities()` vocabulary: `"transactions"`, `"cypher"`,
    `"surrealql"`, `"vector"` (when the graph DB also indexes
    embeddings, e.g. SurrealDB's `INDEX ... HNSW`).
- **`run_graph_conformance(store)`** suite — round-trip nodes/edges,
  pattern match correctness, traversal depth bounds, idempotent
  upsert, capabilities honesty.
- **Frozen value types**: `GraphNode`, `GraphEdge`, `GraphPattern`,
  `GraphMatch`, `Path`.

- **`agentforge-memory-surrealdb`** — implements `MemoryStore` +
  `VectorStore` + `GraphStore` (SurrealDB is genuinely multi-modal).
  Uses the official Python SDK over the WebSocket protocol.
  Capabilities: `{"transactions", "vector", "surrealql",
  "live_query"}`.

- **`agentforge-memory-neo4j`** — implements `MemoryStore` +
  `GraphStore` (Neo4j doesn't have a first-class vector type; users
  needing similarity search pair Neo4j with `agentforge-memory-
  postgres` + pgvector or `agentforge-memory-sqlite` + brute-force).
  Uses the official `neo4j` async driver. Capabilities:
  `{"transactions", "cypher"}`.

- **Agent integration**: `Agent(graph_store=...)` kwarg; surfaced on
  `RuntimeContext.graph_store` for strategies that want to traverse
  a knowledge graph during reasoning. Future feat may add a `GraphRag`
  retriever that combines vector retrieval with graph expansion (the
  industry pattern from Microsoft GraphRAG, LightRAG, etc.).

**Estimated chunks:** 6-7 — ABC + value types + conformance suite,
SurrealDB driver, Neo4j driver, Agent integration, property tests,
CHANGELOG/PR.

**Open questions to resolve at design time:**
- How rich should the `match()` pattern DSL be? Cypher is huge;
  starting with a subset is honest. Initial proposal: tuple-of-
  segments `[(label, edge_type, label), ...]` plus property
  filters as dicts.
- Should the value types live in `agentforge-core` or only in
  the driver packages? Arguments both ways — leaning core for
  consistency with `Claim` / `VectorItem`.
- Vector + graph hybrid search (GraphRAG-style retrieval) is its
  own feature; feat-009 just delivers the contract and drivers.

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
