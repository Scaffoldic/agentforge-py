# feat-025: Neo4jVectorStore (vector + hybrid search via Neo4j VECTOR + FULLTEXT indexes)

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-025 |
| **Title** | `Neo4jVectorStore` — `VectorStore` over Neo4j 5.13+ vector + fulltext indexes |
| **Status** | shipped (Python) |
| **Owner** | kjoshi |
| **Created** | 2026-05-14 |
| **Target version** | 0.2 |
| **Languages** | both (TS deferred to v0.4) |
| **Module package(s)** | `agentforge-memory-neo4j` (adds `Neo4jVectorStore` alongside the existing `Neo4jMemoryStore` + `Neo4jGraphStore`) |
| **Depends on** | feat-005 (VectorStore ABC + drivers), feat-022 (`lexical_search` ABC method + `run_hybrid_search_conformance`), feat-024 v0.3 polish (parameterized migrations) |
| **Blocks** | none |

---

## 1. Why this feature

`agentforge-memory-neo4j` ships `MemoryStore` (claim audit log)
and `GraphStore` (knowledge-graph traversal) but no
`VectorStore` — even though Neo4j 5.13+ has first-class vector
indexes (`CREATE VECTOR INDEX`) and has shipped them as a
production capability since 2023. Operators who pick Neo4j as
their backing store currently have to run a second database
just for vector retrieval; that's friction the framework can
remove.

After feat-025 Neo4j becomes a single-database option for the
full RAG stack: claims + graph + vector + hybrid retrieval
all in one place.

## 2. Why it must ship as framework

- **VectorStore is a framework-locked ABC.** Adding a new
  driver is the standard contribution shape; the framework
  benefits from cross-driver consistency.
- **The `vector_stores` entry-point category** already
  exists (Postgres, SQLite, SurrealDB register there).
  Neo4j is the missing fourth.
- **Hybrid retrieval (feat-022) needs `lexical_search`
  coverage on every shipped VectorStore.** This PR closes
  the Neo4j gap; SurrealDB closes alongside (see
  feat-022 v0.2 follow-up).
- **Without framework ownership:** every Neo4j-deploying
  agent reinvents the vector + fulltext index DDL and the
  Cypher search patterns. The framework's migration
  framework + entry-point registry lets users opt in via
  YAML.

## 3. How derived agents benefit

A scaffolded agent using Neo4j gets vector retrieval with no
code changes:

```yaml
# agentforge.yaml
retrieval:
  vector_store:
    driver: neo4j
    config:
      url: bolt://neo4j:7687
      dimensions: 1536
      auth: [neo4j, "${NEO4J_PASSWORD}"]
  embedder: { driver: bedrock-titan, config: {} }
  mode: hybrid   # feat-022 — both vector AND lexical paths
  top_k: 5
```

`agentforge db migrate` provisions the vector + fulltext +
constraint indexes. `agent.run("...")` uses both retrieval
paths and fuses via RRF (feat-022's standard pipeline).

## 4. Feature specifications

### 4.1 User-facing experience

- `Neo4jVectorStore.from_url(url, *, dimensions, auth,
  database="neo4j")` — ergonomic construction, mirrors
  `Neo4jMemoryStore.from_url`.
- `init_schema()` runs the bundled vector migrations
  (parameterized with `${dimensions}` via feat-024 v0.3).
  After it returns, the store declares
  `{"native_ann", "hybrid_search"}`.
- `search(query_vector, *, limit, filter_metadata)` — cosine
  similarity via the native vector index.
- `lexical_search(query, *, limit, filter_metadata)` — BM25
  via the native fulltext index.
- `delete(ids)` — DETACH DELETE by id; returns the count
  actually removed.

### 4.2 Public API / contract

```python
class Neo4jVectorStore(VectorStore):
    def __init__(
        self,
        *,
        runner: CypherRunner,
        dimensions: int,
        ann_indexed: bool = False,
    ) -> None: ...

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        dimensions: int,
        auth: tuple[str, str],
        database: str = "neo4j",
    ) -> Self: ...

    def migrator(self) -> Neo4jMigrator: ...
    async def init_schema(self) -> None: ...
    # plus the standard VectorStore methods
```

**Node label.** `AfVector` — distinct from `AfNode`
(graph store) so the two coexist in the same database
without overlap. Properties: `af_id: str` (unique),
`embedding: list[float]`, `text: str`, `metadata: map`.

**Indexes** (provisioned by the bundled migration):
- `af_vector_id` — unique constraint on `n.af_id`.
- `af_vector_embedding` — `CREATE VECTOR INDEX ... ON
  (n.embedding) OPTIONS {indexConfig: { 'vector.dimensions':
  ${dimensions}, 'vector.similarity_function': 'cosine' }}`.
- `af_vector_text` — `CREATE FULLTEXT INDEX ... FOR (n:AfVector)
  ON EACH [n.text]`.

**Search Cypher.**
- Vector: `CALL db.index.vector.queryNodes(
  'af_vector_embedding', $limit, $query) YIELD node, score
  RETURN node.af_id, node.text, node.metadata, score`.
  Neo4j returns cosine similarity in `[0, 1]`.
- Lexical: `CALL db.index.fulltext.queryNodes(
  'af_vector_text', $query) YIELD node, score RETURN ...`.
  Returns Lucene-style scores; the driver max-normalises
  to `[0, 1]` per result set (mirrors the SQLite + SurrealDB
  patterns).

**Metadata filter.** Applied client-side after `queryNodes`
returns. Over-fetched by 4× when a filter is set (same
pattern as SQLite). Native Cypher post-filtering (e.g.
`WHERE node.metadata.k = $v`) requires composite indexes;
deferred.

### 4.3 Internal mechanics

- **Migrations** ship at
  `agentforge_memory_neo4j/migrations/vector/`:
  - `0000_migrations_table.cypher` (duplicate of the
    memory-store dir's; identical content + same SHA-256
    checksum so the second store to run skips
    re-applying).
  - `0100_vectors.cypher` — uniqueness constraint + vector
    index + fulltext index, all with `IF NOT EXISTS`.
- **Capability gating** mirrors `PostgresVectorStore`:
  `_ann` flips to True after `init_schema()`; `capabilities()`
  returns `{"native_ann", "hybrid_search"}` only when
  `_ann` is True.
- **Cypher 5.x quirks**: `CREATE VECTOR INDEX` accepts only
  one statement per `run()` call; the migrator already
  handles this via `_split_statements`.

### 4.4 Module packaging

- Lives entirely inside `agentforge-memory-neo4j`. No new
  sister packages.
- `pyproject.toml` gains a new
  `[project.entry-points."agentforge.vector_stores"]`
  group registering `neo4j =
  "agentforge_memory_neo4j.vector:Neo4jVectorStore"`.

### 4.5 Configuration

```yaml
retrieval:
  vector_store:
    driver: neo4j
    config:
      url: bolt://localhost:7687
      dimensions: 1536
      auth: [neo4j, password]
      database: neo4j
  embedder: { driver: bedrock-titan, config: {} }
```

## 5. Plug-and-play & upgrade story

- Existing Neo4j deployments are additive — the new vector
  node label (`AfVector`) doesn't collide with the existing
  `AfNode` (graph) or `Claim` (memory) labels.
- Operators run `agentforge db migrate` once after
  upgrading to provision the new indexes.
- Downgrading: leave the indexes in place; they're harmless
  when the store isn't used.

## 6. Cross-language parity

TypeScript port deferred to v0.4 (same as feat-022 / -023 /
-024). The Cypher patterns + index DDL are reusable
verbatim; the TS port mirrors the Python shape 1:1.

## 7. Test strategy

- **Unit tests** — new `VectorFakeRunner` in
  `tests/unit/conftest.py` that routes vector + fulltext
  Cypher to an `InMemoryVectorStore` + a per-test
  `_BM25Index`. Covers the standard `run_vector_conformance`
  + `run_hybrid_search_conformance` suites.
- **Live tests** (gated on `RUN_LIVE_NEO4J=1`) — exercise
  the actual Cypher against a Neo4j 5.13+ container.
  Live `run_vector_conformance` + `run_hybrid_search_conformance`.
- **Cross-platform** — Python-only client, no native deps.

## 8. Risks & open questions

- **Neo4j 5.13+ required.** Vector indexes shipped in 5.13;
  older versions error on `CREATE VECTOR INDEX`. Documented
  in the runbook; no runtime version check (Neo4j gives a
  clear error).
- **Mixed label coexistence.** `AfNode` (graph) + `AfVector`
  (this PR) + `Claim` (memory) all live in the same
  database. They're isolated by label; users mixing the
  three stores see no semantic crosstalk.
- **Fulltext analyzer.** Defaults to Neo4j's standard
  Lucene tokenizer. Language-aware analyzers are out of
  scope (same as feat-022's English-only restriction).

## 9. Out of scope

- Neo4j graph-augmented retrieval (single-Cypher join of
  vector + graph) — feat-023 sister-package follow-up.
- Custom analyzers / language packs.
- Vector quantization configs.
- TypeScript port (v0.4).
- `down` migrations — feat-024 v0.3+.

## 10. References

- Neo4j 5.x vector index docs:
  `db.index.vector.queryNodes`, `CREATE VECTOR INDEX`.
- Neo4j fulltext index docs:
  `db.index.fulltext.queryNodes`, `CREATE FULLTEXT INDEX`.
- feat-022 spec (hybrid search Protocol).
- feat-024 spec + v0.3 polish (parameterized migrations).

## 11. Implementation status (Python)

**Status: shipped (Python).** Landed in one PR per the
user's "Both in one PR" scope choice. Bundled with the
SurrealDB native `lexical_search` follow-up (a feat-022
sister-package gap that completes hybrid_search coverage
across every shipped `VectorStore`).

Chunked across 3 commits (chunks 2-4 bundled for cohesion):

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `8bfb6a3` | This spec + catalogue row + roadmap pointer. |
| 2-4 | `465b7bd` | `Neo4jVectorStore` class + entry-point registration + `VectorFakeRunner` + Neo4j vector migrations + Neo4j `lexical_search` + SurrealDB `lexical_search` (with `0101_fts.surql` migration via `DEFINE ANALYZER` + `SEARCH ANALYZER ... BM25`). 9 new unit tests across both packages. |
| 5 | this commit | Spec status flip + catalogue + roadmap + CHANGELOG + state. |

### Out-of-scope (deferred)

- Graph-augmented retrieval inside Neo4j / SurrealDB
  (feat-023 sister-package follow-up) — separate PR.
- `down` migrations — feat-024 v0.3+.
- TypeScript port — v0.4.

## 12. Runbook

### How do I use Neo4jVectorStore?

```python
from agentforge_memory_neo4j import Neo4jVectorStore

async with await Neo4jVectorStore.from_url(
    "bolt://localhost:7687",
    dimensions=1536,
    auth=("neo4j", "password"),
) as store:
    await store.init_schema()
    # store now declares {"native_ann", "hybrid_search"}
    await store.upsert(items)
    results = await store.search(query_vec, limit=5)
```

Via YAML:

```yaml
retrieval:
  vector_store:
    driver: neo4j
    config:
      url: bolt://localhost:7687
      dimensions: 1536
      auth: [neo4j, password]
  embedder: { ... }
  mode: hybrid
```

### How do I run live tests locally?

```bash
docker run --rm -d --name neo4j-test \
  -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.20-community

RUN_LIVE_NEO4J=1 NEO4J_URL=bolt://localhost:7687 \
NEO4J_AUTH_USER=neo4j NEO4J_AUTH_PASSWORD=password \
  uv run pytest -m live packages/agentforge-memory-neo4j/tests/integration
```

### When should I NOT use Neo4jVectorStore?

- Pure vector workloads (no graph): pgvector or SQLite are
  lighter.
- Sub-millisecond search at billion-scale: dedicated vector
  DBs (Pinecone, Weaviate, Qdrant) outperform Neo4j's
  index. Use Neo4j when the *combined* vector + graph
  surface justifies single-database operational simplicity.
- Older Neo4j (< 5.13): vector indexes aren't available.
  Use a different driver.
