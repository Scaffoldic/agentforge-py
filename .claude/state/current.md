---
feature: chore-self-contained-project-docs
state: implementing
branch: chore/self-contained-project-docs
started_at: 2026-05-10T13:00
last_milestone_at: 2026-05-10T13:30
last_shipped: feat-005 (Persistence) — partial; sqlite + RAG via PR #5, neo4j + surrealdb + GraphStore via PR #7; postgres via PR #8 (open, awaiting reorg merge)
blocker: null
flags_for_user: []
---

## Active work

Structural reorg, **not a feat-NNN**: agentforge-py becomes
self-contained for AI assistants. Background:

- The previous decoupling PR (#2) removed `../../` references from
  agentforge-py to the parent design workspace's pipeline files but
  did not move those files in. Result: agentforge-py's
  `.claude/CLAUDE.md` reading order pointed at paths that didn't
  exist locally.
- AI sessions reading agentforge-py couldn't find the canonical
  pipeline / feature catalogue / state record at the parent — they
  started inventing feat-NNN numbers from CHANGELOG/roadmap memory.
- That's how PRs #5, #7, #8 ended up labelled feat-007/feat-009/
  feat-008 even though all three actually implement portions of
  canonical feat-005 (Persistence — `MemoryStore` ABC + drivers).

The user picked the structural fix: each project fully
self-contained. Parent workspace stays as the meta layer (universal
pipeline, design principles, ADRs); each sub-project owns its own
feature specs, state, CHANGELOG, AGENTS.md, CLAUDE.md.

## What this PR does

1. **Moves into `agentforge-py`:**
   - All 20 `feat-NNN-*.md` specs + `README.md` catalogue from parent
     `docs/features/` → `agentforge-py/docs/features/`.
   - `state/current.md`, `state/log.md`, `state/README.md` from parent
     `.claude/state/` → `agentforge-py/.claude/state/`.
2. **Updates `agentforge-py/.claude/CLAUDE.md`** so the reading order
   references only files inside this repo.
3. **Updates `agentforge-py/AGENTS.md`** with the full project
   pipeline (analyse → design → implement → test → PR + Implementation
   section update). Self-contained — no upward path traversal.
4. **Updates `docs/roadmap.md`** to point at the now-local
   `docs/features/feat-NNN-*.md`.
5. **Logs the divergence + remediation** in `state/log.md`.
6. **CHANGELOG entry** under `Changed`.

The parent workspace gets non-git updates (deletion of moved
directories, AGENTS.md / CLAUDE.md rewrite to focus on
workspace-level concerns) — those happen out-of-band since the
parent isn't version-controlled.

## After merge

- Rebase `feat/008-postgres` (PR #8) onto the new main. Re-apply the
  chunk-4 doc updates inline with the new structure (Implementation
  section now at `agentforge-py/docs/features/feat-005-*.md` instead
  of the parent path).
- Delete `/Users/khemchandjoshi/MbytesWorkspace/ai-agents/docs/features/`
  and `/Users/khemchandjoshi/MbytesWorkspace/ai-agents/.claude/state/`
  (they live in agentforge-py now).
- Update parent `AGENTS.md` and `.claude/CLAUDE.md` to reflect the
  new workspace-meta-only role.

## Reading order on session resume (post-reorg)

1. `agentforge-py/AGENTS.md`
2. `agentforge-py/.claude/state/current.md` (this file)
3. `agentforge-py/docs/features/README.md` (catalogue) — pick
   the active feature
4. `agentforge-py/docs/features/feat-NNN-*.md` for the active feature
5. `agentforge-py/docs/roadmap.md` (project-level shipped/backlog
   pointer)

The parent workspace's `AGENTS.md` and
`.claude/development-pipeline.md` are still authoritative for
**cross-project** workflow patterns, but **for project-specific
work, this project's files are self-contained**.
