# feat-022: Hybrid search (BM25 + vector fusion)

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-022 |
| **Title** | Hybrid search — BM25 + vector retrieval fused via Reciprocal Rank Fusion |
| **Status** | shipped (Python) |
| **Owner** | kjoshi |
| **Created** | 2026-05-14 |
| **Target version** | 0.2 |
| **Languages** | both (TS deferred to v0.4) |
| **Module package(s)** | `agentforge-core` (ABC extension + BM25 + conformance), `agentforge` (Retriever integration + InMemoryVectorStore native impl) |
| **Depends on** | feat-001 (Agent/contracts), feat-005 (VectorStore + Retriever), feat-021 (optional `Reranker` post-fusion) |
| **Blocks** | none |

---

## 1. Why this feature

Vector retrieval excels at *semantic* matches: it finds
passages whose embedding sits close to the query's
embedding, even when no surface vocabulary overlaps. But
production RAG queries straddle two regimes:

- **Semantic queries** ("how do I fix this crash?") — vector
  retrieval wins because the matching documentation rarely
  echoes the user's exact phrasing.
- **Lexical queries** (proper nouns, error codes, model IDs,
  CLI flags, function names, ULIDs) — vector retrieval
  *under-performs* because embeddings smear specific tokens
  into broad semantic neighbourhoods.

In practice every public RAG benchmark above ~10k documents
shows that vector-only retrieval loses ~5–15 % recall on
keyword-heavy slices. The standard production fix is
**hybrid search**: run BM25 (the classic term-frequency
lexical model) alongside vector search, and fuse the two
ranked lists. Cross-vendor benchmarks (Pinecone, Vespa,
Elastic) consistently show Reciprocal Rank Fusion (RRF)
gives the best zero-tune recall.

Without hybrid retrieval baked into the framework, every
derived agent reinvents this — and most do it badly (score
addition with no calibration, or BM25-then-rerank with no
RRF). feat-022 ships the production default so agent
authors get hybrid behaviour by toggling
`retrieval.mode: hybrid` in `agentforge.yaml`.

## 2. Why it must ship as framework

- **The fusion algorithm is a retrieval-time policy.** Two
  agents over the same corpus should be able to pick vector,
  lexical, or hybrid without rewriting either. Pushing the
  decision into user code locks each agent to one mode.
- **The `VectorStore` capability vocabulary already declares
  `hybrid_search`** (per the ABC docstring at
  `vector_store.py:103`) but doesn't actually have a
  contract method backing it. feat-022 closes that gap so
  drivers can declare hybrid support honestly.
- **Score normalisation is per-path, fusion is per-result.**
  BM25 scores are unbounded positive, cosine similarities
  are `[0, 1]`. Naive score addition is meaningless. RRF
  fuses by *rank*, sidestepping the calibration problem
  entirely — the framework owns this so users never have to
  think about it.
- **Cross-driver consistency.** SQLite has FTS5, Postgres
  has `tsvector`/`ts_rank`, Elastic has BM25 native,
  Pinecone bundles sparse vectors. They all need to map into
  the same `lexical_search(query, *, limit) ->
  list[VectorMatch]` shape — one ABC method, drivers
  translate at the boundary.
- **Without framework ownership:** every agent ships its own
  inverted index + fusion code. Quality varies wildly;
  switching vector stores breaks bespoke setups; nobody can
  benchmark hybrid recall across the ecosystem.

## 3. How derived agents benefit

A scaffolded agent's RAG pipeline becomes:

```yaml
# agentforge.yaml
retrieval:
  mode: hybrid           # <-- enables BM25 + vector fusion
  vector_store: { driver: in-memory, config: { dimensions: 768 } }
  embedder:     { driver: bedrock-titan, config: {} }
  top_k: 5
  over_fetch_factor: 3
  rrf_k: 60              # standard RRF constant (Cormack 2009)
```

No code changes. The same `agent.run("...")` now pulls
candidates from both vector + lexical paths and fuses them.
Existing single-mode agents stay on `mode: vector` (the
default) and behave exactly as before.

## 4. Feature specifications

### 4.1 User-facing experience

- `agentforge.yaml` gains two optional fields under
  `retrieval`: `mode` (`"vector"` default | `"hybrid"`) and
  `rrf_k` (positive int, default 60).
- `Retriever(mode="hybrid", store=store, embedder=embedder,
  ...)` constructs a hybrid retriever directly. Constructor
  raises `ValueError` when the store doesn't declare the
  `"hybrid_search"` capability.
- `Retriever.retrieve(query)` returns top-k `VectorMatch`es
  whose ordering is the RRF-fused rank across the two
  paths. When a `Reranker` is configured, it applies *after*
  fusion (rerank receives the fused candidate set).

### 4.2 Public API / contract

**`VectorStore.lexical_search`** — new default method on
the ABC at `agentforge_core.contracts.vector_store`:

```python
async def lexical_search(
    self,
    query: str,
    *,
    limit: int = 5,
    filter_metadata: dict[str, Any] | None = None,
) -> list[VectorMatch]:
    """Return the top-`limit` items by lexical (BM25-style)
    relevance to `query`.

    Default raises `NotImplementedError`. Drivers that
    declare the `"hybrid_search"` capability MUST override.

    Scores in the returned matches are normalised to [0, 1]
    by max-score division within the result set (so the top
    match has score 1.0; absolute BM25 magnitudes are not
    portable across corpora). Cross-path comparability is
    NOT guaranteed — fuse by rank, not raw score.
    """
```

**Capability key** `"hybrid_search"` — already in the
ABC's closed vocabulary (no change). Drivers opt in by
returning `{"hybrid_search"}` (and any other capabilities)
from `capabilities()`.

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
    ) -> None: ...
```

**`RetrievalConfig`** — extended at
`agentforge_core.config.schema`:

```python
class RetrievalConfig(BaseModel):
    vector_store: ModuleEntry
    embedder: ModuleEntry
    reranker: RerankerEntry | None = None
    top_k: int = 5
    over_fetch_factor: int = 3
    batch_size: int = 32
    mode: Literal["vector", "hybrid"] = "vector"
    rrf_k: int = Field(default=60, ge=1)
```

### 4.3 Internal mechanics

**BM25 (Okapi).** Standard formula:

```
score(D, Q) = Σ_t∈Q  IDF(t) · TF_norm(t, D)

IDF(t) = ln( (N - df(t) + 0.5) / (df(t) + 0.5) + 1 )

TF_norm(t, D) =
   ( tf(t, D) · (k1 + 1) ) /
   ( tf(t, D) + k1 · (1 - b + b · |D| / avg_dl) )
```

Defaults: `k1 = 1.5`, `b = 0.75` (Robertson). Tokeniser
splits on `\W+` after lowercase, drops tokens ≤ 1 char. No
stemming, no stopwords in v0.2 — keeps the dependency
surface zero.

**RRF fusion.** Standard formula (Cormack, Clarke, Büttcher,
SIGIR 2009):

```
RRF_score(d) = Σ_L  1 / (k + rank_L(d))
```

where `rank_L(d)` is `d`'s 1-indexed rank in result list
`L` (omit `L` from the sum when `d` is absent). The
framework uses `k = 60` as the default per the paper.

Implementation pseudocode in `Retriever._rrf_fuse`:

```python
def _rrf_fuse(vec, lex, *, limit, k):
    scores = defaultdict(float)
    matches_by_id = {}
    for rank, m in enumerate(vec, start=1):
        scores[m.id] += 1.0 / (k + rank)
        matches_by_id[m.id] = m
    for rank, m in enumerate(lex, start=1):
        scores[m.id] += 1.0 / (k + rank)
        matches_by_id.setdefault(m.id, m)
    fused = sorted(scores.items(), key=lambda kv: kv[1],
                   reverse=True)[:limit]
    return [matches_by_id[id_].model_copy(update={"score": s})
            for id_, s in fused]
```

**In-memory store.** Lazy `_BM25Index` rebuilt on first
`lexical_search` after any mutation (upsert / delete). A
dirty-flag invalidates the index. Acceptable for the
"hundreds of items" niche the in-memory store targets;
production deployments swap to a driver with a native
lexical path.

**Over-fetch interaction.** Hybrid mode pulls
`limit * over_fetch_factor` from *each* path (so the fuser
sees a wider candidate set than a vector-only retrieve
would). When a `Reranker` is set, the reranker receives the
fused top-`over_fetch_factor * limit` and narrows to
`limit`.

### 4.4 Module packaging

- **ABC + BM25 helper + conformance** ship in
  `agentforge-core` (zero new deps).
- **`Retriever` extension + InMemoryVectorStore native
  hybrid impl** ship in `agentforge`.
- **Driver-native lexical paths** (Postgres `tsvector`,
  SQLite FTS5) ship as follow-up PRs against the existing
  driver packages.

### 4.5 Configuration

`agentforge.yaml`:

```yaml
retrieval:
  mode: hybrid
  vector_store:
    driver: in-memory
    config:
      dimensions: 768
  embedder:
    driver: bedrock-titan
    config: {}
  top_k: 5
  over_fetch_factor: 3
  rrf_k: 60
```

`mode: vector` (default) reverts to feat-021 behaviour.

## 5. Plug-and-play & upgrade story

- Existing `Retriever(...)` calls keep their semantics —
  `mode` defaults to `"vector"`.
- Existing `agentforge.yaml` files keep working —
  `retrieval.mode` defaults to `"vector"`.
- Adding the `"hybrid_search"` capability to an existing
  driver is a minor version bump for that driver (and the
  driver must implement `lexical_search`).

## 6. Cross-language parity

TypeScript port deferred to v0.4 (same as feat-021). The
RRF + BM25 shapes are language-agnostic; the TS port will
mirror this surface 1:1.

## 7. Test strategy

- **`_BM25Index` unit tests** — single doc, multi-doc,
  tokenisation edge cases, `k1`/`b` knobs, delete.
- **`run_hybrid_search_conformance(store)`** — gated suite
  that verifies `lexical_search` behaviour for any store
  declaring `hybrid_search`. The main
  `run_vector_conformance` is unchanged.
- **`Retriever.mode="hybrid"`** integration tests — synthetic
  corpus where vector and lexical disagree, assert RRF
  fuses to the expected order.
- **YAML round-trip** — `tests/integration/test_retrieval_yaml.py`
  extended to load `mode: hybrid` and exercise
  `retrieve()`.
- **Live tests** — none in this PR. Native Postgres /
  SQLite lexical paths land in their own packages and ship
  with `@pytest.mark.live` coverage.

## 8. Risks & open questions

- **BM25 with no stemming/stopwords** may under-perform on
  morphologically rich corpora (e.g. German compounds, Czech
  declensions). Documented in the runbook; v0.3+ may add an
  opt-in tokeniser hook.
- **In-memory store rebuilds the BM25 index from scratch on
  every mutation.** Fine for ≤ 10k items; logged as a
  comment in the impl. Drivers with native lexical paths
  don't hit this.
- **RRF score interpretation:** users sometimes expect
  cosine-like scores `[0, 1]`. RRF scores are
  `[0, ~1/(k+1) · num_lists]`. Documented in the runbook +
  the docstring on `Retriever.retrieve`.

## 9. Out of scope

- Native Postgres `tsvector` / `ts_rank` `lexical_search`
  impl. (Separate PR on `agentforge-memory-postgres`.)
- Native SQLite FTS5 impl. (Separate PR on
  `agentforge-memory-sqlite`.)
- Stemming / stopwords / language-aware tokenisers.
- Weighted-score fusion (alternative to RRF; requires
  calibration).
- GraphRAG hybrid (vector + graph traversal) — separate
  un-numbered sub-feat, likely feat-023.
- TypeScript port (v0.4).

## 10. References

- Cormack, G. V., Clarke, C. L. A., Büttcher, S.
  "Reciprocal Rank Fusion outperforms Condorcet and
  individual rank learning methods." SIGIR 2009.
- Robertson, S. E., Walker, S. "Some simple effective
  approximations to the 2-Poisson model for probabilistic
  weighted retrieval." SIGIR 1994. (Original BM25.)
- Pinecone "Hybrid search" docs;
  Vespa "Hybrid retrieval" docs;
  Elastic "RRF in Elasticsearch 8.8" announcement —
  industry adoption of RRF as the production default.

## 11. Implementation status (Python)

**Status: shipped (Python).** Landed as a single PR per
the user's "Full spec in one PR" scope choice. Chunked
across 5 commits:

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `e42dbbc` | This spec + catalogue row + roadmap pointer. |
| 2 | `588c532` | `VectorStore.lexical_search` default-method + `_BM25Index` helper + `InMemoryVectorStore` native hybrid impl + `run_hybrid_search_conformance` + unit tests. |
| 3 | `f5af6c1` | `Retriever(mode="hybrid", rrf_k=60)` + `_rrf_fuse` (RRF Cormack 2009) + tests covering constructor validation, fused ordering, top_k truncation, vector-mode regression, post-fusion reranker application. |
| 4 | `b2917dd` | `RetrievalConfig.mode` / `rrf_k` + `build_retriever_from_config` forwarding + YAML integration test. |
| 5 | this commit | Spec implementation-status flip + catalogue row flip + roadmap flip + CHANGELOG + state files. |

### Out-of-scope (deferred)

- ~~Postgres `tsvector` / SQLite FTS5 native `lexical_search`
  — separate PRs per driver package.~~ **Shipped** in the
  v0.2 follow-up bundle (see below).
- Stemming / stopwords / language tokenisers — opt-in hook
  v0.3+.
- TypeScript port — v0.4.

### v0.2 follow-up — native Postgres + SQLite lexical paths

Closes the deferred native-driver work in one bundled PR.
Both drivers now declare `"hybrid_search"` and pass
`run_hybrid_search_conformance` end-to-end.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `69a450e` | **Postgres native lexical_search.** `init_schema()` is now idempotent and adds an `embedding_tsv tsvector` generated column over `to_tsvector('english', text)` + a GIN index. Query uses `ts_rank_cd(embedding_tsv, plainto_tsquery('english', $1))` with metadata JSONB containment + max-normalisation at the SQL boundary. Capability `hybrid_search` joins `native_ann` post-init (same gating pattern); calling `lexical_search` before init raises a clear `RuntimeError`. Unit-test fake runner uses `_BM25Index` for directionally identical ordering. |
| 2 | `55c5a38` | **SQLite native lexical_search via FTS5.** `_SCHEMA_SQL` extended with a `vectors_fts` virtual table over `vectors.text` (`unicode61` tokeniser) + three triggers that keep the FTS index in sync on every `INSERT`/`UPDATE`/`DELETE`. Query uses `bm25(vectors_fts)` (negated for DESC ordering, max-normalised). Always declares `hybrid_search` since the schema is provisioned in `from_path()`. User input passes through `_escape_fts_query` so FTS5 special syntax stays literal. |
| 3 | this commit | Spec subsection + catalogue + roadmap flips + CHANGELOG + state. |

### v0.2 follow-up deviations

- **English-only text-search config.** Postgres uses
  `to_tsvector('english', ...)`; SQLite uses the
  language-neutral but unstemmed `unicode61` tokeniser.
  Future config knob (`language: english | german | none`)
  is out-of-scope; documented in the runbook.
- **Postgres capability gating** mirrors `native_ann` — the
  capability is only declared after `init_schema()` runs.
  Without bootstrap the `embedding_tsv` column doesn't
  exist; calling `lexical_search` would silently produce no
  results, so the driver raises instead.

## 12. Runbook

Audience: agent developers wiring up hybrid retrieval.

### How do I enable hybrid retrieval in my agent?

Set `retrieval.mode: hybrid` in `agentforge.yaml`. The
vector store you use must declare the `"hybrid_search"`
capability. The built-in `InMemoryVectorStore` does;
follow-up PRs add it to the Postgres and SQLite drivers.

```yaml
retrieval:
  mode: hybrid
  vector_store: { driver: in-memory, config: { dimensions: 768 } }
  embedder:     { driver: bedrock-titan, config: {} }
  top_k: 5
```

That's all. `agent.run("...")` now pulls candidates from
both paths and fuses them.

### How do I tune RRF?

The default `rrf_k=60` is the value from the original RRF
paper and matches the production defaults at Pinecone /
Vespa / Elastic. Raising `k` flattens the score curve (each
list's contribution becomes more uniform across ranks);
lowering it sharpens it (top-ranked items dominate). In
practice tuning `k` rarely moves recall by more than 1–2 %;
the production-quality knob is `over_fetch_factor`, which
controls the candidate-set width feeding the fuser.

### When should I NOT use hybrid?

- Pure-semantic corpora (image captions, transcribed
  speech) where users never query specific tokens.
- Latency-sensitive paths under 50 ms — running two
  retrieval calls doubles wall time (the parallel
  `asyncio.gather` mitigates only partially).
- Corpora under ~100 documents — vector retrieval alone
  is already saturating recall.

### How does hybrid mode interact with reranking?

The reranker (if set) sees the **fused** candidate set, not
the raw vector or lexical lists. This is the production
default — rerankers are trained on `(query, candidate)`
pairs and don't care which path surfaced the candidate.
