---
feature: v0.2.0 cut — providers + runbooks + trackers + release coordination
state: in_review
branch: chore/v0.2-trackers-alignment
started_at: 2026-05-14
last_milestone_at: 2026-05-14
last_shipped: feat-020 v0.3 polish — sentence-window streaming output guardrails (PR #48 merged 2026-05-14)
blocker: null
flags_for_user: []
---

## Active feature

Bundled v0.2.0 release PR (#49) — four commits on
`chore/v0.2-trackers-alignment`:

1. **chore: align trackers ahead of v0.2.0 cut** (a185a84) —
   roadmap fixes + v0.3 backlog + feat-003 catalogue.
2. **feat(feat-003): ship 5 first-party LLM provider sister
   packages** (f01e9e0) — `agentforge-anthropic`, `-openai`,
   `-voyage`, `-litellm`, `-ollama`. Runner-Protocol +
   lazy-SDK-import pattern. ~7000 LoC.
3. **docs(feat-019): add 5 v0.2 runbooks + provider-table polish**
   (926ccdf) — runbooks 17–21 inside `_shared/docs/runbooks/`.
4. **chore(release): cut v0.2.0** (40d498e) — all 34 packages
   bumped to 0.2.0 + CHANGELOG flip + roadmap "Tagged
   releases" table.

PR URL: https://github.com/Scaffoldic/agentforge-py/pull/49

## Post-merge tasks

- `git tag v0.2.0 && git push --tags`
- Smoke `pip install agentforge-anthropic[anthropic]` from a
  built wheel.

## Last shipped

feat-020 v0.3 polish — sentence-window streaming output
guardrails (PR #48 merged 2026-05-14).

### Previously

- feat-025 — Neo4jVectorStore + SurrealDB native
  lexical_search (PR #47).
- feat-024 v0.3 polish — parameterized migrations (PR #46).
- feat-024 — Schema migrations framework (PR #45).
- feat-023 — GraphRAG hybrid retrieval (PR #44).
- feat-022 v0.2 follow-up — native hybrid for Postgres +
  SQLite (PR #43).
- feat-022 — BM25 + vector hybrid search (PR #42).

## Next pick candidates (v0.3+)

- `down` migrations / schema rollback (feat-024 v0.3+).
- Native single-Cypher graph-augmented retrieval inside
  Neo4j / SurrealDB (feat-023 sister-package follow-up).
- Multi-cluster Redlock for `RedisSessionLock`
  (feat-020 v0.3+).
- True streaming-aware `stream-then-redact` (feat-020 v0.3+).
- Evidently real-time drift dashboards via Cloud
  (feat-009 v0.3+).
- Optional eval sister packages (`-ragas` / `-deepeval` /
  `-toxicity` / `-codeexec`).
- TypeScript port of the v0.2 surface.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
