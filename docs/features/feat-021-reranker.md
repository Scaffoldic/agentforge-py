# feat-021: Reranker

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-021 |
| **Title** | Reranker — cross-encoder reranking on top of vector retrieval |
| **Status** | shipped (Python) |
| **Owner** | kjoshi |
| **Created** | 2026-05-13 |
| **Target version** | 0.2 |
| **Languages** | both (TS deferred to v0.4) |
| **Module package(s)** | `agentforge-core` (ABC), `agentforge` (Retriever integration), `agentforge-reranker-sentence-transformers` (default concrete) |
| **Depends on** | feat-001 (Agent/contracts), feat-003 (EmbeddingClient), feat-005 (VectorStore + Retriever) |
| **Blocks** | none |

---

## 1. Why this feature

Vector search gives recall — it pulls every passage that's
semantically close to the query — but the ranking it returns
is approximate. The top-1 match from a 1M-document corpus is
rarely the most relevant document for an LLM-grounded
answer; the relevant one tends to be somewhere in the
top-20. Cross-encoder reranking is the standard production
fix: pull a bigger candidate set from the vector store, then
score each `(query, candidate)` pair with a dedicated model
that's trained to predict relevance directly.

Every production RAG stack ships reranking. LangChain has
`Cohere Rerank`, LlamaIndex has `SentenceTransformerRerank`,
Haystack has `TransformersSimilarityRanker`. Without
reranking, derived agents degrade as the corpus grows past a
few thousand documents — vector-only retrieval becomes the
quality ceiling.

## 2. Why it must ship as framework

- **Reranker is a retrieval-time policy decision**, not an
  agent-internal concern. Two agents over the same corpus
  should be able to plug in different rerankers without
  rewriting either.
- **The `Retriever` integration surface is the framework's
  business.** `Retriever.retrieve(query, top_k=K)` is the
  consumer-facing call site; it decides whether to
  over-fetch from `VectorStore` and rerank, or not. Pushing
  that decision to user code means every agent reinvents
  over-fetch.
- **Score normalisation contract** — cross-encoders return
  raw logits in vendor-specific ranges (`[-10, 10]` for
  SentenceTransformers, `[0, 1]` for Cohere, etc.). The
  framework owns the normalisation so downstream code can
  filter / threshold portably.
- **Cross-vendor consistency.** SentenceTransformers, Cohere,
  Voyage, Mixedbread, ColBERT — they all take `(query,
  candidates)` and return scored ranks. One ABC, vendor
  modules behind it.
- **Without framework ownership:** every agent's reranker
  wiring is bespoke; over-fetch / score thresholding logic
  fragments; cross-vendor swap is a rewrite, not a config
  change.

## 3. How derived agents benefit

- **One config-line upgrade for any RAG agent.** Add
  `retrieval.reranker:` to `agentforge.yaml`, get
  cross-encoder reranking on every retrieval call. No tool
  code changes.
- **Vendor-agnostic.** Swap SentenceTransformers ↔ Cohere ↔
  Voyage in YAML; no consumer code change.
- **Same `VectorMatch` shape on the wire.** The reranker
  returns the same shape the consumer already handles —
  only the `score` field changes.
- **Cost-controllable over-fetch.** `over_fetch_factor=3`
  is the default (pull 3× the requested top-k, rerank to
  top-k); tune up for harder queries, down to disable.

## 4. Feature specifications

### 4.1 User-facing experience

```python
from agentforge import Agent, Retriever
from agentforge_reranker_sentence_transformers import (
    SentenceTransformersReranker,
)
from agentforge_memory_sqlite import SqliteVectorStore

reranker = SentenceTransformersReranker.from_config(
    model="cross-encoder/ms-marco-MiniLM-L-6-v2",
)
retriever = Retriever(
    vector_store=SqliteVectorStore(...),
    embedding_client=...,
    reranker=reranker,
    over_fetch_factor=3,
)

results = await retriever.retrieve("how do I deploy?", top_k=5)
# 5 reranked VectorMatch — pulled 15 from the vector store,
# reranked to top 5 by the cross-encoder.
```

Via config (preferred):

```yaml
retrieval:
  vector_store:
    name: sqlite
    config:
      path: ./vectors.db
  reranker:
    name: sentence-transformers
    config:
      model: cross-encoder/ms-marco-MiniLM-L-6-v2
    over_fetch_factor: 3
```

### 4.2 Public API / contract

```python
# agentforge_core/contracts/reranker.py — locked
class Reranker(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[VectorMatch],
        *,
        top_k: int | None = None,
    ) -> list[VectorMatch]:
        """Re-sort `candidates` by relevance to `query`.

        Returns a new list (no mutation) sorted descending by
        the reranker's score. Each returned `VectorMatch` has
        its `score` field replaced with the reranker's
        normalised score (still in `[0, 1]`); other fields
        (`id`, `text`, `metadata`) pass through unchanged.

        When `top_k` is None, returns all candidates re-sorted.
        When set, truncates to the top `top_k` after sorting.
        """

    async def close(self) -> None:
        """Release any held resources (model handles, HTTP clients)."""

    def capabilities(self) -> set[str]:
        """Optional capabilities — `"local"` (runs offline),
        `"managed"` (calls external API), `"batched"`
        (accepts batched query-candidate pairs)."""
        return set()
```

```python
# agentforge.retrieval.Retriever — extended
class Retriever:
    def __init__(
        self,
        *,
        vector_store: VectorStore,
        embedding_client: EmbeddingClient,
        reranker: Reranker | None = None,
        over_fetch_factor: int = 3,
        ...
    ) -> None: ...

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorMatch]: ...
```

### 4.3 Internal mechanics

```
Retriever.retrieve(query, top_k=K)
  │
  ├── (1) Embed query → query_vector
  ├── (2) over_fetch = K * over_fetch_factor if reranker else K
  ├── (3) vector_matches = await vector_store.search(
  │           query_vector, limit=over_fetch, filter_metadata=...)
  ├── (4) if reranker:
  │           return await reranker.rerank(query, vector_matches, top_k=K)
  └── (5) else: return vector_matches[:K]
```

Score normalisation lives in the concrete reranker, not the
ABC. The ABC's contract is `score ∈ [0, 1]`; concrete impls
must apply whatever transformation (sigmoid for
SentenceTransformers, identity for Cohere) to satisfy it.

### 4.4 Module packaging

| Package | Provides |
|---|---|
| `agentforge-core` | `Reranker` ABC, conformance suite |
| `agentforge` | `Retriever` integration |
| `agentforge-reranker-sentence-transformers` | Default concrete impl wrapping `CrossEncoder.predict` |
| (future) `agentforge-reranker-cohere` | Cohere managed-API reranker |
| (future) `agentforge-reranker-voyage` | Voyage managed-API reranker |
| (future) `agentforge-reranker-mixedbread` | Mixedbread managed-API reranker |
| **custom** | Implement `Reranker`; register via `agentforge.rerankers` entry-point |

The sister-package pattern from feat-009 v0.2 vendor backends
applies: each concrete impl ships a `_runner.py` Protocol +
production runner under `# pragma: no cover` + in-memory
fake in `src/_inmem_runner.py`. SDK is an optional extra
(`pip install agentforge-reranker-sentence-transformers[sentence-transformers]`).

### 4.5 Configuration

See §4.1 YAML example. The `retrieval.reranker:` block is
resolved via the existing module-discovery machinery
(feat-010); `name` maps to an `agentforge.rerankers`
entry-point. Both `agentforge.yaml` and direct
`Retriever(reranker=...)` work side-by-side.

## 5. Plug-and-play & upgrade story

`agentforge add module reranker-sentence-transformers`
installs + wires (via feat-011 scaffolding). Removing is
`agentforge remove module reranker-sentence-transformers`.
The `Retriever.reranker=None` default keeps existing agents
unaffected by the package's presence in the venv.

Upgrade safety: ABC signature is locked at v0.2; adding
optional kwargs to `rerank()` (e.g. a `score_threshold`)
behind defaults is minor-bump compatible per ADR-0007.

## 6. Cross-language parity

TS port lands by v0.4 with the rest of feat-005 retrieval
surface. Wire-format is language-neutral (`VectorMatch` is a
plain JSON object); the ABC's shape translates directly.

## 7. Test strategy

- **ABC conformance:** every concrete impl passes
  `run_reranker_conformance(reranker)` — identity-rerank
  test, descending-sort test, `top_k` truncation, empty
  candidates, score-range invariants.
- **Retriever integration:** inject `FakeVectorStore` +
  `FakeReranker` (reverses order); assert
  `retrieve(top_k=3, over_fetch_factor=2)` pulls 6 from the
  store and reranks to 3. `over_fetch_factor=1` skips
  rerank.
- **Score normalisation:** sentence-transformers concrete
  asserts sigmoid maps raw `-10 → ~0`, `0 → 0.5`, `+10 → ~1`.
- **Live test:** `@pytest.mark.live` downloads
  `cross-encoder/ms-marco-MiniLM-L-6-v2` (~80MB) and
  reranks three known candidates deterministically. Gated
  on `RUN_LIVE_RERANKER=1`.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Cross-encoder latency on cold start | Documented; users pre-warm models in `agentforge run --preload` |
| Reranker becomes a cost surface (managed APIs) | Reranker calls go through the existing budget reservation (feat-007); each `rerank()` call commits its cost |
| Over-fetch multiplies vector-store load | `over_fetch_factor=1` disables; users tune per agent |
| Score normalisation hides ranking quality differences | The reranker's `score` is normalised, but ordering is unchanged — downstream consumers see the same rank |
| Concurrent reranks on a single CrossEncoder model | SentenceTransformers' `CrossEncoder.predict` is thread-safe; we add an internal lock in the production runner for asyncio safety |

## 9. Out of scope

- **ColBERT-style late-interaction rerankers.** Different
  contract (token-level scoring, not pair scoring). Track
  as a separate sub-feat.
- **Auto-tuning `over_fetch_factor`** based on hit rate.
  v0.3+; manual tuning ships first.
- **Streaming reranking** (per-token rerank as the LLM emits
  candidates). Not a real use case yet.
- **Vendor reranker sister packages** beyond
  sentence-transformers (`-cohere`, `-voyage`, `-mixedbread`)
  — separate v0.2.x sub-feat PRs, same shape.

## 10. References

- [`architecture.md`](../design/architecture.md) §3
  (retrieval pipeline)
- feat-005 (VectorStore + Retriever)
- ADR-0007 (versioning + contract evolution)

---

## 11. Implementation status (Python)

**Status: shipped (Python).** Landed in one PR per the user-
chosen "ABC + SentenceTransformers default + Retriever
integration" scope. Five chunks; each gated through
`uv run pre-commit run --all-files` before being recorded.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `0118b4f` | Canonical `docs/features/feat-021-reranker.md` spec + `docs/features/README.md` row under new "Retrieval" subsection + roadmap cross-reference. |
| 2 | `6c5a198` | `Reranker` ABC at `agentforge_core/contracts/reranker.py` — async `rerank(query, candidates, *, top_k=None)`, `close()`, `capabilities()` / `supports()`. Re-exported from `agentforge_core` top-level. `run_reranker_conformance()` shipped in `agentforge_core.testing` — nine invariants (empty input, top_k<1 raises, top_k=None returns all, top_k truncates, scores in [0,1], descending sort, non-mutation of id/text/metadata, input immutability, unknown capability returns False). Two reference impls (Identity / Reverse) in tests pass it. |
| 3 | `6edf080` | `Retriever.__init__` gains `reranker: Reranker | None = None` + `over_fetch_factor: int = 3`. `retrieve(query, top_k=K)` pulls `K * over_fetch_factor` from the store and reranks to `K` when set, falls back to plain `K` slicing otherwise. `close()` propagates to the reranker. `.reranker` property exposes the injected instance; constructor validates `over_fetch_factor >= 1`. |
| 4 | `fbe6d50` | New workspace member `agentforge-reranker-sentence-transformers`. `SentenceTransformersReranker(runner=...)` + `.from_config(model=...)` builder. Builds `(query, text)` pairs, forwards through runner.predict, applies numerically-stable sigmoid to satisfy `score ∈ [0, 1]`, sorts + truncates. `CrossEncoderRunner` Protocol + `_SentenceTransformersRunner` (`# pragma: no cover`) wrapping the SDK; `FakeCrossEncoderRunner` in `src/_inmem_runner.py` with scripted `set_scores` + `predict_calls` recorder. Capabilities `{"local", "batched"}`. Entry-point `agentforge.rerankers:sentence-transformers` registered. |
| 5 | (this PR) | Spec §11 + §12 + CHANGELOG `[Unreleased]/Added + Changed` + roadmap flip + state. |

### Deviations from this spec

- **No `retrieval.reranker:` YAML resolver wiring shipped.**
  Spec §4.5 sketches the config-block. The `Reranker` entry-
  point is registered (`agentforge.rerankers:sentence-
  transformers`) but the resolver glue that maps
  `retrieval.reranker.name` → a `Reranker` instance + auto-
  wires it into the `Retriever` is deferred. Direct
  `Retriever(reranker=...)` works today; config-driven wiring
  lands in a follow-up alongside the next vendor reranker
  package.
- **Default `over_fetch_factor=3` matches Cohere's docs**;
  Voyage suggests 5, SentenceTransformers' own examples use
  2. We picked 3 as the middle of the cluster + the most
  cited value.
- **Cross-encoder thread safety.** The production runner
  doesn't yet hold an internal lock; the spec hinted at
  one. CrossEncoder.predict is reportedly thread-safe at the
  PyTorch level; adding an asyncio.Lock around it can ship
  as a v0.2.x patch if reports surface.

### Open items

- Vendor reranker sister packages
  (`agentforge-reranker-cohere`, `-voyage`,
  `-mixedbread`) — each is the same shape as
  `agentforge-reranker-sentence-transformers` (Protocol +
  runner + fake + entry-point), one PR per vendor.
- `retrieval.reranker:` YAML resolver wiring (above).
- ColBERT-style late-interaction rerankers — different
  contract (token-level scoring); separate spec when
  picked up.
- TS port.

---

## 12. Runbook

### How do I add reranking to an existing Retriever?

```bash
pip install agentforge-reranker-sentence-transformers[sentence-transformers]
```

```python
from agentforge import Retriever
from agentforge_reranker_sentence_transformers import (
    SentenceTransformersReranker,
)

reranker = SentenceTransformersReranker.from_config(
    model="cross-encoder/ms-marco-MiniLM-L-6-v2",
)
retriever = Retriever(
    store=vector_store,
    embedder=embedding_client,
    reranker=reranker,
    over_fetch_factor=3,
)
results = await retriever.retrieve("how do I deploy?", top_k=5)
```

The retriever now pulls `5 * 3 = 15` candidates from the
vector store and asks the reranker to choose the best 5.

### How do I write a custom Reranker?

Implement the ABC; register the entry-point.

```python
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.values.vector import VectorMatch


class MyReranker(Reranker):
    async def rerank(
        self,
        query: str,
        candidates: list[VectorMatch],
        *,
        top_k: int | None = None,
    ) -> list[VectorMatch]:
        if top_k is not None and top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        if not candidates:
            return []
        # Score each (query, candidate.text) pair however you like;
        # the only contract is that scores end up in [0, 1] and
        # the returned list is sorted descending.
        scored = await _your_scoring(query, candidates)
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_k] if top_k else scored

    async def close(self) -> None:
        return None

    def capabilities(self) -> set[str]:
        return {"managed"}
```

Register via `pyproject.toml` entry-point:

```toml
[project.entry-points."agentforge.rerankers"]
my-reranker = "my_pkg:MyReranker"
```

### How do I tune `over_fetch_factor`?

The default `3` is a sane middle. Higher values (5–10) buy
more recall at the cost of vector-store load + reranker
latency. Lower values (1–2) cut cost but risk losing the
relevant document before the reranker sees it.

Two rules of thumb:

- If the corpus is small (< 10k docs), `over_fetch_factor=1`
  with no reranker is usually enough.
- If the corpus is large (> 100k docs) and quality matters
  more than latency, push `over_fetch_factor` to 5 or 10.

### How do I run the live reranker test?

```bash
RUN_LIVE_RERANKER=1 \
    uv run pytest -m live \
    packages/agentforge-reranker-sentence-transformers/
```

The test downloads the
`cross-encoder/ms-marco-MiniLM-L-6-v2` model (~80MB) on
first run and reranks three known candidates against a
deterministic query.
