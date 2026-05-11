---
feature: feat-010b-destructive-cli
state: implementing
branch: feat/010b-destructive-cli
started_at: 2026-05-11T22:00
last_milestone_at: 2026-05-11T22:00
last_shipped: feat-012 (Configuration system) shipped via PR #17 @ 758780f
blocker: null
flags_for_user: []
---

## Active feature

**feat-010 destructive-CLI sub-feat** — `agentforge add/swap/remove
module X` commands deferred from feat-010 (PR #16). Tracked under
the feat-010 spec's "destructive-CLI sub-feat (deferred)" entry in
`docs/roadmap.md`.

User decision (2026-05-11): Option A — do the destructive CLI
before feat-011 (Scaffolding & upgrade). feat-011 will consume
the same manifest-apply machinery; shipping it here first means
feat-011 stays scoped to scaffolding without re-inventing the
manifest format.

## Scope

| Piece | Where |
|---|---|
| **`Manifest` value type** — env_vars, templates, config_block, next_steps | `agentforge-core/values/manifest.py` |
| **`AppliedManifest` state value type** — what got written, for `remove` to reverse | `agentforge-core/values/manifest.py` |
| **Manifest discovery** — load `<package>/manifest.yaml` via `importlib.resources` | `agentforge/cli/manifest_apply.py` |
| **Idempotent applier**: env vars append (skip if present), templates copy with marker, agentforge.yaml insert, state write to `.agentforge-state/manifests/<dist>.yaml` | `agentforge/cli/manifest_apply.py` |
| **Reverser**: un-append env vars, delete copied files, un-insert config block | same module |
| **`agentforge add module <name>`** | `agentforge/cli/module_cmd.py` |
| **`agentforge swap <category> <from> <to>`** | same |
| **`agentforge remove module <name>`** | same |
| **`pip` subprocess wrapper** — `python -m pip install/uninstall` in active venv | same |

## Design decisions

- **Manifest path inside the package**: convention is
  `<package import name>/manifest.yaml` discovered via
  `importlib.resources.files(<package>).joinpath("manifest.yaml")`.
- **Distribution → package**: `agentforge-memory-sqlite` →
  `agentforge_memory_sqlite` (replace `-` with `_`).
- **State directory**: `.agentforge-state/manifests/<dist>.yaml`
  in the cwd. Created on first `add`; gitignored as a runbook
  recommendation (not enforced).
- **Idempotency**: re-running `agentforge add module X` on an
  already-applied module is a no-op + "already applied" line.
- **YAML edits**: plain `pyyaml` (already a dep). `safe_load` /
  `safe_dump` — round-trip loses comments and key order; document
  the trade-off. Escalate to `ruamel.yaml` if users complain.
- **`agentforge add` calls `python -m pip install`** (not `uv
  add`): works in any venv (uv, hatch, plain venv). Detecting
  `uv` and switching is a follow-up.
- **Marker headers** for copied template files:
  `# AGENTFORGE-MANAGED: <dist>` (or `// ` for JS, `<!-- -->` for
  HTML — derive from extension). Allows `remove` to be sure it's
  only deleting framework-managed files.
- **Atomicity**: not transactional. If apply fails mid-way, the
  state file is updated to reflect what *did* land so `remove`
  can clean up partially. Document this.

## Proposed chunks (4 total)

1. **`Manifest` + `AppliedManifest` value types + manifest applier**
   (pure data layer, no subprocess, no pip). Idempotent functions
   for env-var append, template copy + marker, YAML config insert,
   state write. Reverser for each. Tests against an in-memory
   fake module dir.

2. **`agentforge add module <dist>`** — pip subprocess + manifest
   discovery + applier call + state write + next-steps print. Mock
   pip in tests (don't actually install).

3. **`agentforge remove module <dist>`** + **`agentforge swap
   <category> <from> <to>`** — reverse applier; swap composed as
   remove + add with a single state-aware transaction.

4. **Docs + PR**: update feat-010 spec's Implementation status —
   move `add/swap/remove` from "What's not yet implemented" into a
   new section; add Runbook entries; CHANGELOG; raise PR
   (`docs(feat-010)` since it completes feat-010, not a new
   feat-NNN).

## TODO

- [x] User approved Option A — destructive CLI before feat-011.
- [ ] Chunks 1-4 implementation.
- [ ] PR.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/features/feat-010-module-discovery-and-cli.md`
