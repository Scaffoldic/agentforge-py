---
feature: feat-021 v0.2 follow-up — retrieval: YAML block
state: in_review
branch: chore/feat-021-retrieval-yaml-resolver-wiring
started_at: 2026-05-14
last_milestone_at: 2026-05-14
last_shipped: feat-021 (Reranker ABC + SentenceTransformers default + Retriever integration) shipped via PR #37 (merged 2026-05-13)
blocker: null
flags_for_user: []
---

## Active feature

[`feat-021 — Reranker`](../../docs/features/feat-021-reranker.md)
v0.2 follow-up — closes the deferred config-driven wiring
from feat-021's initial PR. Per user-chosen "Full retrieval:
block + Retriever builder" scope.

- **`retrieval:` top-level YAML block** —
  `RetrievalConfig` + `RerankerEntry` Pydantic models;
  validates vector_store / embedder / reranker against
  their existing entry-point groups.
- **`build_retriever_from_config()`** — resolves all three
  sub-components, checks ABC conformance, threads top_k /
  over_fetch_factor / batch_size into the Retriever
  constructor.
- **`_instantiate()` factory helper** — prefers keyword
  expansion (`cls.from_config(**cfg)`) to support keyword-
  only `from_config` signatures.

## Last shipped

[`feat-021 — Reranker`](../../docs/features/feat-021-reranker.md)
ABC + SentenceTransformers default + Retriever integration
shipped via PR #37 (merged 2026-05-13).

### Previously

- feat-009 v0.2 — Langfuse + Phoenix + Evidently + StatsD
  vendor observability backends (PR #36, 2026-05-13).
- feat-014 v0.3 — A2A per-token streaming + unified
  `StreamingChunkKind` (PR #35, 2026-05-13).
- feat-020 v0.2 — postgres + redis history + slack adapter +
  per-token streaming foundation (PR #34, 2026-05-13).

## Next pick candidates

We're mid-v0.2.0 cycle. Sequence continues v0.3 → v0.4 → 1.0
per [ADR-0015](../../docs/adr/0015-coordinated-release-train.md).

**Remaining backlog:**

- **Vendor reranker sister packages** — `agentforge-
  reranker-cohere`, `-voyage`, `-mixedbread`. Same shape as
  the sentence-transformers package; one PR per vendor.
- **Sub-feat backlog (still un-numbered)** — GraphRAG
  hybrid retrieval, BM25 + vector hybrid search, schema
  migrations.
- **Strategy-level streaming overrides** — concrete
  `ReasoningStrategy.stream` impls on `ReActLoop` etc.
- **feat-009 v0.3 polish** — child OTel spans, A2A trace
  propagation, content-based PII redaction.
- **`Agent(retriever=...)` constructor kwarg** — currently
  the builder returns a sibling `Retriever`; agents wire it
  into tools manually. Bumped to v0.3 if usage patterns
  warrant.

**Already shipped on the v0.1 → v0.2 line:**

- feat-013 v0.2 — production MCP runner (PR #32).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33).
- feat-020 v0.2 — chat history + adapters + streaming
  (PR #34).
- feat-014 v0.3 — A2A per-token streaming + unified
  `StreamingChunkKind` (PR #35).
- feat-009 v0.2 — vendor backends (PR #36).
- feat-021 — Reranker ABC + sentence-transformers default
  + Retriever integration (PR #37).
- feat-021 v0.2 follow-up — `retrieval:` YAML block +
  builder (in review).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
