# State files — session continuity

The framework's development is iterative across many sessions. These
files keep the history and the current snapshot so any AI assistant
(or human) resuming work can pick up exactly where the last session
ended.

## Files

| File | Purpose | Lifecycle |
|---|---|---|
| `current.md` | The single live snapshot — feature in progress, branch, state, design notes, blockers | Overwritten as state changes |
| `log.md` | Append-only milestone log across all features | Append-only |
| `feature-progress/feat-NNN.md` *(optional)* | Per-feature scratchpad if the snapshot gets too long | Created on feature start, archived on shipped |

## When to read

- **Always at session start.** The first thing an AI assistant working
  on this repo does is read `AGENTS.md` and `state/current.md`.
- **Before any pipeline transition.** Before moving from one stage to
  the next, re-read the current state to confirm assumptions.
- **Before raising a PR.** Confirm the log captures every milestone on
  this branch.

## When to write

- **At every pipeline state transition.** Update `current.md`'s `state:`
  field. Append a one-line entry to `log.md`.
- **At every committed milestone.** Append to `log.md`: a heading with
  date and event, then a few lines of detail.
- **At every PR open and every merge** (especially in a multi-PR feature
  cluster, e.g. a release's bug-fix train). Refresh `current.md`
  (`feature:`, `branch:`, `state:`, the `flags_for_user:` PR list, the
  pickup list) and append a `log.md` milestone, then **commit and push
  both on the current branch** — don't wait for session end. The tracker
  must always reflect which PRs are merged vs in-flight so any resume
  (this clone or another) sees the true state. This cadence is mirrored
  in the workspace pipeline (Rule 4 + "Pausing mid-feature").
- **When a blocker appears.** Update `current.md > blocker:` with a
  description; the user will see it on next session resume.
- **When you find a bug from a previous feature.** Append a
  `[BUG-CARRIED]` entry to `log.md` under the active feature.
- **At session end / when pausing mid-feature.** Update `current.md`
  (`state:`, a `resume:` marker, and a concrete pickup list with open
  PR URLs + branch names), append a dated `log.md` milestone, then
  **commit and push both** on the current branch. Never leave
  `current.md` / `log.md` as a local-only working-tree change — unpushed
  state is invisible to a resume from another clone and silently drifts.
  Rule of thumb: if someone else pulled right now, could they continue?

## Pre-commit enforcement

> **Note:** the `check_state_updated.py` hook described below is not
> currently wired into `.pre-commit-config.yaml` (aspirational). State
> currency is maintained by the "When to write" discipline above until
> the hook lands.

`scripts/check_state_updated.py` runs on every commit and verifies:

- `current.md`'s mtime is within 24 hours of the commit (or the only
  changes in the commit don't touch `src/`).
- `log.md` mtime is within 24 hours.
- `current.md > feature` matches the active branch (`feat/NNN-slug`).

Failures block the commit.

## current.md format

A single YAML-fronted markdown file. The YAML block is structured;
the prose below is free-form notes.

```markdown
---
feature: feat-NNN-slug
state: idle | analysing | designing | implementing | testing | pre-commit | committed | pushed | pr-raised | shipped | blocked
branch: feat/NNN-slug
started_at: 2026-05-09T14:30
last_milestone_at: 2026-05-09T16:42
last_shipped: feat-XXX @ <sha>
blocker: null | "<description>"
flags_for_user: []
---

## Analysis notes
- ...

## Design notes
- ...

## TODO before next milestone
- [ ] ...

## Bug carries on this feature
- [BUG-CARRIED] feat-PRIOR: <description> — fixed in <commit-or-pending>
```

## log.md format

Append-only. Newest entries at the bottom (chronological).

```markdown
## 2026-05-09T14:30 — feat-001 started
Branch: feat/001-core-contracts-and-agent

## 2026-05-09T16:42 — feat-001 design approved
Decision: Pydantic v2 for all value types, no bare dataclasses on public surface.

## 2026-05-10T09:15 — [BUG-CARRIED] feat-007 idempotency keying broke when run_id had hyphens
Fixed in: <commit-sha-on-feat-001-branch>
Test added: tests/unit/test_idempotency_special_chars.py

## 2026-05-12T17:20 — feat-001 shipped
PR: <url>
Commit on main: <sha>
Coverage on diff: 94.3%
```

## When `current.md` gets too long

If notes for a single feature grow beyond ~150 lines, move them to
`feature-progress/feat-NNN.md` and link from `current.md`. The snapshot
should stay scannable.

After the feature ships, the `feature-progress/feat-NNN.md` is
appended to `log.md` (compressed) and deleted from
`feature-progress/`.

## What this is NOT

- **Not a Kanban / project tracker.** Use the feature catalogue
  (`docs/features/README.md`) for the "what's in flight" question
  beyond the current feature.
- **Not a public artefact.** State files are framework-development
  meta; not read by users of AgentForge agents.
- **Not an issue tracker.** During v0.x, bug-carries live here; after
  v1.0, defects against shipped features become `bug-NNN` docs (and
  `state/log.md` records that they were filed).
