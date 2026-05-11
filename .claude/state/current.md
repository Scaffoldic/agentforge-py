---
feature: none
state: idle
branch: main
started_at: null
last_milestone_at: 2026-05-11T23:59
last_shipped: feat-011 shipped via PR #19 (awaiting merge)
blocker: null
flags_for_user: []
---

## Active feature

*None — awaiting next pick.*

## Last shipped

[`feat-011 — Scaffolding & upgrade`](../../docs/features/feat-011-scaffolding-and-upgrade.md)
shipped in PR #19 with full Python scope:

- `agentforge new <name>` + 6 starter templates rendered via
  Copier (`minimal`, `code-reviewer`, `patch-bot`, `docs-qa`,
  `triage`, `research`).
- `.agentforge-state/managed-files.lock` + `AGENTFORGE-MANAGED:`
  marker headers (per-extension comment styles).
- `agentforge upgrade` via Copier's three-way merge.
- `agentforge fork` / `unfork` / `status`.
- 12 + 23 unit tests; templates ship in-wheel via hatchling
  force-include.

Deviations recorded in the spec §10:

- Templates ship in-wheel (not in a separate
  `agentforge-templates` repo) — keeps v0.x installs network-free.
- `unfork` is partially restorative; full content re-render
  happens on the next `agentforge upgrade`.
- `--run-tests` on upgrade deferred.
- TypeScript engine (ADR-0021) deferred.

## Next pick candidates (canonical numbering)

- **feat-013** — MCP integration (consume MCP tool servers; expose
  agent tools as MCP server).
- **feat-014** — A2A protocol support (cross-framework agent calls).
- **feat-017** — CLI runtime expansion (`run`, `eval`, `db`, ...).
- **feat-019** — Developer experience + AI assistant rules (the
  Runbook scaffold + AGENTS.md / CLAUDE.md / .cursorrules).
- Vendor observability sub-feats (`agentforge-langfuse`,
  `agentforge-phoenix`, `agentforge-evidently`, `agentforge-statsd`).

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
