---
feature: feat-010b-destructive-cli
state: pre-pr
branch: feat/010b-destructive-cli
started_at: 2026-05-11T22:00
last_milestone_at: 2026-05-11T22:45
last_shipped: feat-012 (Configuration system) shipped via PR #17 @ 758780f
blocker: null
flags_for_user: []
---

## Active feature

**feat-010 destructive-CLI sub-feat** — completes feat-010's full
surface. The read-only half shipped under PR #16; this PR adds
`agentforge add/remove/swap module` now that feat-012's manifest
validation primitives are in.

All 4 chunks landed. Ready to push + raise PR.

## Chunks shipped

| Chunk | Commit | Scope |
|---|---|---|
| 1 | `dadc6c4` | `Manifest` / `EnvVarEntry` / `TemplateFile` / `AppliedManifest` value types + idempotent applier (`apply_manifest` / `reverse_manifest` / `read_applied`). |
| 2-3 | `f2c323c` | `agentforge add/remove/swap module` commands with injectable pip runner. |
| 4 | (this commit) | Update feat-010 spec Implementation status; add Runbook entries for destructive commands; CHANGELOG; roadmap (remove "deferred" sub-feat block). |

## Next after this PR merges

1. Sync main, delete `feat/010b-destructive-cli` local + remote.
2. **feat-011 (Scaffolding & upgrade)** is now the natural pick.
   Deps feat-010 ✓ (now actually complete — manifest format and
   destructive CLI both shipped). feat-011 will use the same
   applier machinery to scaffold new agent repos.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. After merge: `docs/features/feat-011-scaffolding-and-upgrade.md`
