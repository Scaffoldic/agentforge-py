---
feature: feat-020 v0.3 polish — sentence-window streaming output guardrails
state: in_review
branch: chore/feat-020-sentence-window-guardrails
started_at: 2026-05-14
last_milestone_at: 2026-05-14
last_shipped: feat-025 — Neo4jVectorStore + SurrealDB native lexical_search shipped via PR #47 (merged 2026-05-14)
blocker: null
flags_for_user: []
---

## Active feature

Closes the deferred safety gap from feat-020 v0.2: per-token
streamed text on `ChatSession.stream()` now passes through
output validators at sentence boundaries when
`safety_mode == "sentence-window"` (or its current alias
`"stream-then-redact"`). Default `"buffer-then-stream"` is
unchanged.

- New `_SentenceWindowBuffer` at
  `agentforge_chat/_window.py`.
- `ChatSessionConfig.safety_mode` Literal expanded.
- `SafetyMode` re-exported from `agentforge_chat`.
- `ChatSession.__init__` gains `safety_mode=` kwarg;
  `_stream_per_token` dispatches accordingly.
- `build_chat_session_from_config` reads
  `modules.chat.session.safety_mode` and forwards it.

## Last shipped

feat-025 — Neo4jVectorStore + SurrealDB native
lexical_search shipped via PR #47 (merged 2026-05-14).

### Previously

- feat-024 v0.3 polish — parameterized migrations
  (PR #46).
- feat-024 — Schema migrations framework (PR #45).
- feat-023 — GraphRAG hybrid retrieval (PR #44).
- feat-022 v0.2 follow-up — native hybrid for Postgres +
  SQLite (PR #43).
- feat-022 — BM25 + vector hybrid search (PR #42).
- feat-002 + feat-009 v0.3.x strategy follow-ups bundle
  (PR #41).
- feat-002 + feat-009 v0.3 polish + feat-021 follow-up
  bundle (PR #40).

## Next pick candidates

Remaining v0.3+ open items:

- **`down` migrations / schema rollback** (feat-024
  v0.3+).
- **Native single-query graph-augmented retrieval inside
  Neo4j / SurrealDB** (feat-023 sister-package
  follow-up).
- **Evidently real-time drift dashboards via Cloud**
  (feat-009 v0.3+).
- **Multi-cluster Redlock for `RedisSessionLock`**
  (feat-020 v0.3+).

**Already shipped on the v0.1 → v0.2 line:**

- feat-013 v0.2 — production MCP runner (PR #32).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33).
- feat-020 v0.2 — chat history + adapters + streaming
  (PR #34).
- feat-014 v0.3 — A2A per-token streaming (PR #35).
- feat-009 v0.2 — vendor observability backends (PR #36).
- feat-021 — Reranker ABC + Retriever integration
  (PR #37).
- feat-021 v0.2 follow-up — `retrieval:` YAML block +
  builder (PR #38).
- feat-021 v0.2 follow-up — vendor reranker sister
  packages (PR #39).
- feat-002 + feat-009 v0.3 polish + feat-021 follow-up
  bundle (PR #40).
- feat-002 + feat-009 v0.3.x strategy follow-ups bundle
  (PR #41).
- feat-022 — BM25 + vector hybrid search (PR #42).
- feat-022 v0.2 follow-up — native hybrid for Postgres
  + SQLite (PR #43).
- feat-023 — GraphRAG hybrid retrieval (PR #44).
- feat-024 — Schema migrations framework (PR #45).
- feat-024 v0.3 polish — parameterized migrations
  (PR #46).
- feat-025 — Neo4jVectorStore + SurrealDB native
  lexical_search (PR #47).
- feat-020 v0.3 polish — sentence-window streaming
  output guardrails (in review).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
