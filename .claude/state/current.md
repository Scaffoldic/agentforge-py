---
feature: null
state: idle
branch: main
started_at: null
last_milestone_at: 2026-05-15
last_shipped: v0.2.0 — Drivers (PR #49 merged 2026-05-15; tag v0.2.0 pushed; GitHub Release published)
blocker: null
flags_for_user:
  - "Branch protection on `main` still references old job name `Test (ubuntu-latest, Python 3.13)`. Update required status checks to `Test (Linux, Python 3.13)` from the split CI workflows."
  - "PyPI publish for the 16 new packages (5 LLM providers + 4 reranker vendors + 4 observability backends + chat-history-postgres / -redis / -slack) — uv build + twine upload, or wait for CI publish automation."
---

## Active feature

**None.** v0.2.0 shipped 2026-05-15. Pick the next feature from
the v0.3 backlog when ready.

## Last shipped

**v0.2.0 — Drivers** (2026-05-15)

- Merge commit: `70d79c3` (PR #49).
- Tag: `v0.2.0` annotated at the merge commit.
- GitHub Release: <https://github.com/Scaffoldic/agentforge-py/releases/tag/v0.2.0>.
- Release notes file: `docs/releases/v0.2.0.md`.
- 34 workspace packages at `0.2.0`; 16 new sister packages
  introduced in this cycle.
- Theme: every locked v0.1 ABC (`LLMClient`, `EmbeddingClient`,
  `VectorStore`, `GraphStore`, `Reranker`, `Migrator`, chat
  history) now has at least one shipped driver in tree. MCP +
  A2A production runners live. Vendor observability backends
  ship. AI-assistant scaffold now includes GitHub Copilot
  alongside Claude Code / Cursor / Aider.

### Previously

- feat-020 v0.3 polish — sentence-window streaming guardrails
  (PR #48 merged 2026-05-14).
- feat-025 — Neo4jVectorStore + SurrealDB native lexical_search
  (PR #47).
- feat-024 v0.3 polish — parameterized migrations (PR #46).
- feat-024 — Schema migrations framework (PR #45).
- feat-023 — GraphRAG hybrid retrieval (PR #44).
- feat-022 v0.2 follow-up — native hybrid for Postgres +
  SQLite (PR #43).
- feat-022 — BM25 + vector hybrid search (PR #42).

## Next pick candidates (v0.3+)

From `docs/roadmap.md` backlog:

- `down` migrations / schema rollback (feat-024 v0.3+).
- Native single-Cypher / SurrealQL graph-augmented retrieval
  inside Neo4j / SurrealDB (feat-023 sister-package follow-up).
- Multi-cluster Redlock for `RedisSessionLock`
  (feat-020 v0.3+).
- True streaming-aware `stream-then-redact` (regex-inline
  redaction without buffering) (feat-020 v0.3+).
- Evidently real-time drift dashboards via Cloud
  (feat-009 v0.3+).
- Optional eval sister packages (`-ragas` / `-deepeval` /
  `-toxicity` / `-codeexec`).
- TypeScript port of the v0.2 surface (target: v0.4).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
