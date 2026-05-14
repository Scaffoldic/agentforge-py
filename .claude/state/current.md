---
feature: feat-002 + feat-009 v0.3 polish + feat-021 follow-up bundle
state: in_review
branch: chore/feat-002-009-021-streaming-otel-spans-a2a-tracecontext-retriever-wiring
started_at: 2026-05-14
last_milestone_at: 2026-05-14
last_shipped: feat-021 vendor reranker sister packages shipped via PR #39 (merged 2026-05-14)
blocker: null
flags_for_user: []
---

## Active feature

Bundled v0.3 polish PR closing five surfaces in one go per
user-chosen "Full bundle as described" scope:

- **feat-002** — `ReActLoop.stream()` per-iteration override.
- **feat-009 v0.3** — child OTel spans
  (`strategy.iteration` / `llm.call` / `tool.<name>` /
  `evaluator.<name>`), A2A W3C TraceContext propagation,
  content-based PII redaction.
- **feat-021** — `Agent(retriever=...)` auto-wired from
  `build_agent_from_config`.

## Last shipped

feat-021 vendor reranker sister packages
(`agentforge-reranker-cohere`, `-voyage`, `-mixedbread`)
shipped via PR #39 (merged 2026-05-14).

### Previously

- feat-021 v0.2 follow-up — `retrieval:` YAML block +
  `build_retriever_from_config` (PR #38).
- feat-021 — Reranker ABC + sentence-transformers default
  + Retriever integration (PR #37).
- feat-009 v0.2 — Langfuse + Phoenix + Evidently + StatsD
  vendor observability backends (PR #36).
- feat-014 v0.3 — A2A per-token streaming + unified
  `StreamingChunkKind` (PR #35).
- feat-020 v0.2 — postgres + redis history + slack adapter
  + per-token streaming foundation (PR #34).

## Next pick candidates

Remaining v0.2 backlog:

- **Sub-feat backlog (still un-numbered)** — GraphRAG
  hybrid retrieval, BM25 + vector hybrid search, schema
  migrations.
- **ToT + MultiAgent `stream()` overrides** — feat-002
  follow-up; each strategy's iteration shape is different.
- **`strategy.iteration` spans on ToT + MultiAgent** —
  feat-009 v0.3.x; needs a small extract-method refactor.
- **Plan-Execute `stream()` override** — feat-002 follow-up.

**Already shipped on the v0.1 → v0.2 line:**

- feat-013 v0.2 — production MCP runner (PR #32).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33).
- feat-020 v0.2 — chat history + adapters + streaming
  (PR #34).
- feat-014 v0.3 — A2A per-token streaming + unified
  `StreamingChunkKind` (PR #35).
- feat-009 v0.2 — vendor observability backends (PR #36).
- feat-021 — Reranker ABC + sentence-transformers default
  + Retriever integration (PR #37).
- feat-021 v0.2 follow-up — `retrieval:` YAML block +
  builder (PR #38).
- feat-021 v0.2 follow-up — vendor reranker sister
  packages (PR #39).
- feat-002 + feat-009 v0.3 polish + feat-021 follow-up
  bundle (in review).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
