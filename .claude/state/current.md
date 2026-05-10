---
feature: feat-004-tools-system
state: pr-raised
branch: feat/004-tools-system
started_at: 2026-05-10T14:00
last_milestone_at: 2026-05-10T17:15
last_shipped: feat-005 (Persistence) shipped via PRs #5 (sqlite + RAG), #7 (graph + neo4j + surrealdb), #8 (postgres); chore PR #9 (self-contained project layout) merged at 74ea4ed
blocker: null
flags_for_user: []
---

## Active feature

[`feat-004 — Tools system`](../../docs/features/feat-004-tools-system.md)

PR #10 raised. Awaiting review + merge.

## Chunks shipped

| Chunk | Commit | What |
|---|---|---|
| 1 | `6ec7c13` | `@tool` decorator |
| 2 | `97e2acc` | `calculator` + `file_read` |
| 3 | `c5be0f5` | `shell` + `web_search` |
| 4 | `20c9dc6` | `_dispatch_tool` helper + ReAct/PlanExecute refactor |
| 5 | `4ac290a` | `FakeTool` test helper |
| 6 | (this) | CHANGELOG + Implementation section + PR + ruff hook id migrate |

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/features/README.md`
5. `docs/features/feat-NNN-*.md` (active feature)
6. `docs/roadmap.md`

## After merge

- Pull main, delete `feat/004-tools-system` local + remote.
- Pick the next feature per pipeline §1: lowest-numbered proposed
  with deps shipped. Eligible after feat-004:
  - **feat-007** (Production rails) — deps feat-001 ✓ feat-003 ✓
  - **feat-008** (Findings) — deps feat-001 ✓
  - feat-006 (Evaluators) — blocked by feat-008
  - feat-009 (Observability) — blocked by feat-007
  - feat-010 (Module discovery) — blocked by feat-012
- Lowest-numbered eligible is **feat-007** by default.
