# feat-023: GraphRAG hybrid retrieval

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-023 |
| **Title** | GraphRAG hybrid retrieval — vector top-k + N-hop graph expansion |
| **Status** | shipped (Python) |
| **Owner** | kjoshi |
| **Created** | 2026-05-14 |
| **Target version** | 0.2 |
| **Languages** | both (TS deferred to v0.4) |
| **Module package(s)** | `agentforge-core` (`GraphExpansion` value type + config schema), `agentforge` (`Retriever` extension) |
| **Depends on** | feat-001 (Agent/contracts), feat-005 (`GraphStore` + `VectorStore` + `Retriever`), feat-021 (optional `Reranker` post-expansion), feat-022 (optional hybrid base) |
| **Blocks** | none |

---

## 1. Why this feature

Vector retrieval surfaces semantically *similar* passages.
Hybrid (BM25 + vector) surfaces passages that match by
keyword *or* by meaning. But neither captures
**relationships** between documents — citations,
authorship, "responds to", "explains", "is a kind of". For
many production knowledge bases (research libraries, code
search, support articles, biomedical literature) the
*neighbourhood* of a retrieved document is exactly what the
LLM needs to ground its answer.

GraphRAG is the standard production fix:

1. Vector-search for top-k seeds.
2. Traverse the graph from each seed, collect connected
   nodes, deduplicate.
3. Optionally rerank the expanded set.

LangChain has `GraphRAGRetriever`; LlamaIndex has
`KnowledgeGraphRAGRetriever`; Microsoft's GraphRAG project
ships an entire pipeline around the same idea. Without it,
derived agents lose recall on queries where the *answer*
lives one hop away from the query's lexical / semantic
match.

## 2. Why it must ship as framework

- **Graph expansion is a retrieval-time policy decision.**
  Two agents over the same corpus should be able to pick
  vector, hybrid, or graphrag retrieval without rewriting
  either. Pushing the orchestration into user code locks
  each agent to one shape.
- **The `GraphStore` and `Retriever` surfaces are already
  the framework's business.** feat-005 locked them; this
  feature wires the two together so users don't have to.
- **Score-decay + dedupe semantics need cross-driver
  consistency.** Without framework ownership every agent
  invents its own (mostly buggy) merge step.
- **Composes with the existing modes.** Graph expansion is
  orthogonal to vector / hybrid / reranker. The framework
  enforces a clean pipeline: `(base retrieve) →
  (graph expand?) → (rerank?)`.
- **Without framework ownership:** every agent ships its
  own traversal + dedup code; switching graph stores
  breaks bespoke setups; nobody can benchmark recall
  across the ecosystem.

## 3. How derived agents benefit

A scaffolded agent's RAG pipeline becomes:

```yaml
retrieval:
  mode: hybrid                # optional; vector or hybrid base
  vector_store: { driver: in-memory, config: { dimensions: 768 } }
  embedder:     { driver: bedrock-titan, config: {} }
  graph_expansion:
    store: { driver: neo4j, config: { uri: bolt://localhost:7687 } }
    max_hops: 2
    edge_types: [CITES, AUTHORED_BY]
    text_property: text
    decay: 0.5
```

No code changes. The same `agent.run("...")` now pulls
candidates from the vector path, expands each hit through
the graph, and (when a reranker is configured) reranks the
augmented set. Agents that don't want GraphRAG simply omit
the `graph_expansion` block.

## 4. Feature specifications

### 4.1 User-facing experience

- `agentforge.yaml` gains an optional `graph_expansion`
  block under `retrieval`.
- `Retriever(graph_expansion=GraphExpansion(...))`
  constructs a graphrag-capable retriever directly.
  Graph expansion composes orthogonally with `mode` and
  `reranker`.
- `Retriever.retrieve(query)` returns top-k
  `VectorMatch`es that include both direct hits and their
  graph neighbours. Expansion nodes carry the seed match's
  metadata for traceability (`agentforge.expanded_from`,
  `agentforge.hop`).

### 4.2 Public API / contract

**`GraphExpansion`** — new frozen Pydantic value at
`agentforge_core.values.retrieval`:

```python
class GraphExpansion(BaseModel):
    """Graph-traversal configuration for `Retriever` post-retrieve
    augmentation."""

    model_config = ConfigDict(
        frozen=True, strict=True, arbitrary_types_allowed=True
    )

    store: GraphStore
    max_hops: int = 2                       # >= 1
    edge_types: tuple[str, ...] | None = None
    text_property: str = "text"
    decay: float = 0.5                      # in (0, 1]
```

**`Retriever`** — extended constructor at
`agentforge.retrieval`:

```python
class Retriever:
    def __init__(
        self,
        *,
        store: VectorStore,
        embedder: EmbeddingClient,
        top_k: int = 5,
        batch_size: int = 32,
        reranker: Reranker | None = None,
        over_fetch_factor: int = 3,
        mode: Literal["vector", "hybrid"] = "vector",
        rrf_k: int = 60,
        graph_expansion: GraphExpansion | None = None,   # new
    ) -> None: ...
```

**`RetrievalConfig`** — extended at
`agentforge_core.config.schema`:

```python
class GraphExpansionConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    store: ModuleEntry          # graph_stores category
    max_hops: int = Field(default=2, ge=1)
    edge_types: tuple[str, ...] | None = None
    text_property: str = "text"
    decay: float = Field(default=0.5, gt=0.0, le=1.0)


class RetrievalConfig(BaseModel):
    # ... existing fields ...
    graph_expansion: GraphExpansionConfig | None = None
```

### 4.3 Internal mechanics

**Expansion algorithm.** For each top-k base hit:

1. `graph_store.traverse(start_id=hit.id,
   edge_types=cfg.edge_types, max_depth=cfg.max_hops,
   limit=K)` — returns one or more `Path` objects.
2. For each `Path`, walk the nodes; collect unique node
   ids per `(node_id, depth)`, skipping the seed itself.
3. Synthesise a `VectorMatch` per expansion node:
   - `id` ← node id
   - `text` ← `node.properties.get(text_property, "")`
   - `score` ← `seed.score * decay ** depth`
   - `metadata` ← node properties merged with
     `{"agentforge.expanded_from": seed.id,
     "agentforge.hop": depth}`

**Merge + dedup.** Direct hits keep their original scores
and order at the head. Expansion nodes follow, sorted by
score desc. If an expansion node has the same id as a
direct hit, the direct hit wins — its score is higher and
it is already in the head.

**Reranker layering.** Pipeline order is
`(base retrieve) → (graph expand?) → (rerank?)`. The
reranker (when set) sees the *expanded* candidate set, not
the raw base hits.

**Id namespace convention.** `VectorMatch.id` and
`GraphNode.id` are assumed to align — caller's contract.
Documented in the runbook. The framework does not enforce
the alignment; graph expansion silently skips hits whose
ids have no node in the graph store (logged at DEBUG so
operators can spot misconfiguration).

### 4.4 Module packaging

- **`GraphExpansion` value + config schema** ship in
  `agentforge-core`.
- **`Retriever` extension** ships in `agentforge`.
- **No new sister-package.** Reuses the existing
  `graph_stores` entry-point category populated by
  `agentforge-memory-neo4j` and
  `agentforge-memory-surrealdb`.

### 4.5 Configuration

`agentforge.yaml`:

```yaml
retrieval:
  mode: hybrid
  vector_store:
    driver: in-memory
    config: { dimensions: 768 }
  embedder:
    driver: bedrock-titan
    config: {}
  graph_expansion:
    store:
      driver: neo4j
      config:
        uri: bolt://localhost:7687
        user: neo4j
        password: ${NEO4J_PASSWORD}
    max_hops: 2
    edge_types: [CITES, AUTHORED_BY]
    text_property: text
    decay: 0.5
  top_k: 5
```

Omit `graph_expansion` to disable graphrag (default
behaviour).

## 5. Plug-and-play & upgrade story

- Existing `Retriever(...)` calls keep their semantics —
  `graph_expansion` defaults to `None`.
- Existing `agentforge.yaml` files keep working — the new
  block is optional.
- Adding a graph store driver (already supported by the
  `graph_stores` entry-point group) is enough to plug
  GraphRAG into any agent.

## 6. Cross-language parity

TypeScript port deferred to v0.4 (same as feat-021 / -022).
The expansion algorithm, score decay, and dedupe rules are
language-agnostic; the TS port mirrors this surface 1:1.

## 7. Test strategy

- **`GraphExpansion` value validation** — `max_hops < 1`,
  `decay <= 0` or `> 1` raise.
- **`Retriever(graph_expansion=...)` unit tests** —
  single-hop / multi-hop expansion, edge-type filtering,
  score decay, dedupe between vector + expansion hits,
  missing-graph-node handling, reranker post-expansion,
  composition with `mode="hybrid"`.
- **YAML round-trip** — `tests/integration/test_retrieval_yaml.py`
  loads `retrieval.graph_expansion` and exercises
  `retrieve()`.
- **Live tests** — none in this PR. Neo4j / SurrealDB
  drivers already ship with `@pytest.mark.live` coverage;
  GraphRAG-specific live tests follow when a user requests
  them.

## 8. Risks & open questions

- **Id-namespace alignment** is a caller's contract.
  Misconfiguration silently degrades to "no expansion".
  We log a DEBUG line per skipped seed so operators can
  audit; we don't fail-loud because mixed corpora
  (vectors for some docs, graph for others) are common in
  practice.
- **Expansion blow-up.** Dense graphs (high fan-out) can
  explode the candidate set. We cap the merged set at
  `candidate_width * (1 + max_hops)` and rely on the
  reranker (when set) to narrow.
- **No "vector lookup by id"** in the v0.1 `VectorStore`
  ABC. Expansion synthesises matches from graph node
  properties, not from the vector store. Users wanting
  the original vector score for an expanded node must
  re-embed; future v0.3+ may add `VectorStore.get(id)`.

## 9. Out of scope

- Native graph-augmented retrieval inside Neo4j /
  SurrealDB (single Cypher / SurrealQL query combining
  vector + graph). Separate per-driver follow-up.
- Multi-step "agentic" graph traversal (LLM decides next
  hop).
- `VectorStore.get(id)` for re-fetching original scores —
  separate v0.3+ ABC change.
- TypeScript port (v0.4).

## 10. References

- Edge, D. et al. "From Local to Global: A GraphRAG
  Approach to Query-Focused Summarization." Microsoft
  Research (2024).
- LlamaIndex `KnowledgeGraphRAGRetriever` docs.
- LangChain `GraphRAGRetriever` docs.
- Cormack 2009 RRF paper (feat-022 reference) — same
  decision: fuse / merge ranked lists; here merging is
  by id rather than by rank.

## 11. Implementation status (Python)

**Status: shipped (Python).** Landed as a single PR per
the user's "Full spec in one PR" scope choice. Chunked
across 4 commits:

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `5192abf` | This spec + catalogue row + roadmap pointer. |
| 2 | `5f4ce61` | `GraphExpansion` value at `agentforge_core/values/retrieval.py` (frozen, strict, `arbitrary_types_allowed=True` for the `GraphStore` field). `Retriever.__init__` gains `graph_expansion: GraphExpansion \| None = None`. `retrieve()` refactored into a unified pipeline `(base retrieve) → (graph expand) → (rerank)`; new `_expand_via_graph` runs `store.traverse()` per seed in parallel, synthesises a `VectorMatch` per neighbour node (text from `node.properties[text_property]`; `score = seed.score * decay**depth`; metadata carries `agentforge.expanded_from` + `agentforge.hop`), dedup by id with direct hits winning. Unit tests cover validation, single/multi-hop, edge-type filter, score decay, dedup, missing-graph-node tolerance, reranker post-expansion, hybrid composition. |
| 3 | `d588e1b` | New `GraphExpansionConfig` Pydantic block under `RetrievalConfig.graph_expansion`. `build_retriever_from_config` resolves the graph store under the `graph_stores` category, converts `edge_types` (list[str]) to tuple at the boundary, constructs the `GraphExpansion` value, forwards into `Retriever`. Integration test exercises a YAML with `graph_expansion: { max_hops: 2, edge_types: [CITES] }`. |
| 4 | this commit | Spec implementation-status flip + catalogue + roadmap + CHANGELOG + state. |

### Out-of-scope (deferred)

- Native graph-augmented retrieval inside Neo4j /
  SurrealDB — sister-package follow-up.
- `VectorStore.get(id)` ABC addition — v0.3+.
- TypeScript port — v0.4.

## 12. Runbook

Audience: agent developers wiring up GraphRAG.

### How do I enable GraphRAG in my agent?

Add a `graph_expansion` block to `retrieval` in
`agentforge.yaml`. The graph store must declare under
the `graph_stores` entry-point group; the built-in
`InMemoryGraphStore` is registered in tests, and
`agentforge-memory-neo4j` / `agentforge-memory-surrealdb`
register the production drivers.

```yaml
retrieval:
  mode: vector
  vector_store: { driver: in-memory, config: { dimensions: 768 } }
  embedder:     { driver: bedrock-titan, config: {} }
  graph_expansion:
    store: { driver: neo4j, config: { uri: bolt://... } }
    max_hops: 2
    edge_types: [CITES]
```

`agent.run("...")` now expands every vector hit by walking
`CITES` edges up to 2 hops. The expanded nodes appear in
the retrieval result set carrying
`metadata["agentforge.expanded_from"]` so downstream code
can audit provenance.

### How do I align vector ids with graph node ids?

Use the same id when inserting:

```python
await retriever.add_documents(["Paris is..."], ids=["doc-paris"])
await graph_store.add_node(GraphNode(id="doc-paris", labels=("Doc",)))
```

`VectorMatch.id == GraphNode.id` is the convention. The
framework doesn't enforce it; mismatched ids silently
skip expansion for that seed (logged at DEBUG).

### How do I tune `max_hops` and `decay`?

- `max_hops`: 1 for tight, surgical expansion; 2 for the
  typical RAG sweet spot; 3+ only if the graph is sparse.
  Each hop multiplies the candidate set by the average
  fan-out, so tune cautiously.
- `decay`: 0.5 (default) means a 2-hop neighbour scores
  ¼ of the seed. Raise toward 1 to weight far neighbours
  more; lower toward 0 to keep direct hits dominant.

### When should I NOT use GraphRAG?

- No knowledge graph in the corpus (most chat assistants).
- Pure-semantic queries with no relational structure
  (image captions, transcribed speech).
- Latency-sensitive paths — every seed triggers a graph
  traversal; budget accordingly.

### How does GraphRAG interact with reranking and hybrid?

Pipeline order (when all features enabled):

1. **Base retrieve** — vector (or hybrid, if
   `mode="hybrid"`) at `top_k * over_fetch_factor`.
2. **Graph expand** — each base hit walks the graph.
3. **Rerank** — the reranker sees the *expanded* set and
   narrows to `top_k`.

This is the production-default layering. Disable any
stage independently by omitting the relevant config.
