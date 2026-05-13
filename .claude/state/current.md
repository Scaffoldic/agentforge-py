---
feature: feat-021 — Reranker
state: in_review
branch: feat/021-reranker
started_at: 2026-05-13
last_milestone_at: 2026-05-13
last_shipped: feat-009 v0.2 vendor backends shipped via PR #36 (merged 2026-05-13)
blocker: null
flags_for_user: []
---

## Active feature

[`feat-021 — Reranker`](../../docs/features/feat-021-reranker.md)
canonical spec + ABC + Retriever integration + default
SentenceTransformers concrete impl. Promoted from the
un-numbered sub-feat backlog (feat-005 follow-up). Single PR
per user-chosen "ABC + SentenceTransformers default +
Retriever integration" scope.

- **`Reranker` ABC** in `agentforge_core.contracts.reranker`
  — `rerank(query, candidates, *, top_k=None)` + `close()` +
  `capabilities()`/`supports()`.
- **`run_reranker_conformance()`** in
  `agentforge_core.testing` — nine invariants.
- **`Retriever(reranker=..., over_fetch_factor=3)`** —
  pulls `K * factor` from the vector store + reranks to `K`.
- **`agentforge-reranker-sentence-transformers`** — wraps
  `CrossEncoder.predict` + sigmoid-normalises raw logits.

## Last shipped

[`feat-009 v0.2`](../../docs/features/feat-009-observability.md)
vendor observability backends (Langfuse + Phoenix +
Evidently + StatsD) shipped via PR #36 (merged 2026-05-13).

### Previously

- feat-014 v0.3 — A2A per-token streaming + unified
  `StreamingChunkKind` (PR #35, 2026-05-13).
- feat-020 v0.2 — postgres + redis history + slack adapter +
  per-token streaming foundation (PR #34, 2026-05-13).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33, 2026-05-12).
- feat-013 v0.2 — production MCP runner (PR #32).

## Next pick candidates

We're mid-v0.2.0 cycle. Sequence continues v0.3 → v0.4 → 1.0
per [ADR-0015](../../docs/adr/0015-coordinated-release-train.md).

**Remaining backlog (post-feat-021):**

- **Vendor reranker sister packages** — `agentforge-reranker-
  cohere`, `-voyage`, `-mixedbread`. Same shape as the
  sentence-transformers package; one PR per vendor.
- **`retrieval.reranker:` YAML resolver wiring** — config-
  driven Retriever wiring (feat-021 deferred this).
- **Sub-feat backlog (still un-numbered)** — GraphRAG hybrid
  retrieval, BM25 + vector hybrid search, schema migrations.
- **Strategy-level streaming overrides** — concrete
  `ReasoningStrategy.stream` impls on `ReActLoop` etc.
- **feat-009 v0.3 polish** — child OTel spans, A2A trace
  propagation, content-based redaction.

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
  + Retriever integration (in review).

After v0.2.0 lands, v0.3.0 is reserved for the next round
of community / ecosystem feedback. v0.4.0 brings TypeScript
to parity per
[ADR-0002](../../docs/adr/0002-multi-language-python-typescript.md).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
