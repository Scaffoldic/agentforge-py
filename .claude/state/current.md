---
feature: feat-011-scaffolding-and-upgrade
state: implementing
branch: feat/011-scaffolding-and-upgrade
started_at: 2026-05-11T23:00
last_milestone_at: 2026-05-11T23:00
last_shipped: feat-010 destructive CLI shipped via PR #18 @ 4a8f394
blocker: null
flags_for_user: []
---

## Active feature

[`feat-011 — Scaffolding & upgrade`](../../docs/features/feat-011-scaffolding-and-upgrade.md)

Deps: feat-010 ✓ (now genuinely complete with destructive CLI).
User chose Option A — full scope in one PR (`new` + 6 templates +
`upgrade` + `fork`/`unfork`/`status`).

## Scope

| Piece | Where |
|---|---|
| Copier dependency | `agentforge` pyproject |
| **`agentforge new <name>` + Copier templates inline** in `agentforge/templates/<name>/` | new |
| **6 templates**: `minimal`, `code-reviewer`, `patch-bot`, `docs-qa`, `triage`, `research` | inline |
| **Lock file** at `.agentforge-state/managed-files.lock` ({path: {hash, source_module, source_version}}) | new |
| **Marker headers** `AGENTFORGE-MANAGED: <module>@<version> hash:<sha256-prefix>` | new |
| **`agentforge upgrade`** via Copier's 3-way merge | new |
| **`agentforge fork`/`unfork`/`status`** | new |

## Design decisions

- **Templates ship inside `agentforge` package** (`agentforge/templates/<name>/`) accessed via `importlib.resources`. Documented as a deviation from spec §4.4 (separate `agentforge-templates` repo). Migration to a separate repo is a small 0.4 follow-up — Copier accepts either local path or git URL as source.
- **Copier as the engine** (per ADR-0005). Three-way merge handled by `copier update` natively — no custom merge logic.
- **Marker header format** locked per spec §4.2: `AGENTFORGE-MANAGED: <module>@<version> hash:<sha256-prefix>`. `<module>` is `template:<template-name>` for files from `new`, `<dist>` for files from `add module`.
- **Lock file format**: YAML at `.agentforge-state/managed-files.lock`. Per-file entries record `hash` (sha256 of contents at scaffold time), `source_module`, `source_version`, plus optional `forked: true` flag.
- **`agentforge new` flow**: pick template → prompt for answers (`--no-prompts` for batch) → render via Copier → write marker headers post-render → compute hashes + write lock → install dependencies (skip if uv not available — document).

## Proposed chunks (6 total)

1. **Copier dep + `agentforge new` + minimal template**. Wire `agentforge new <name> [--template] [--no-prompts]`; ship `agentforge/templates/minimal/` (single agent script + agentforge.yaml + pyproject + tests).
2. **5 more templates**: code-reviewer, patch-bot, docs-qa, triage, research. Each a working starter with tools / prompts / tests.
3. **Lock file + marker headers**: write `.agentforge-state/managed-files.lock` after `new`; add `AGENTFORGE-MANAGED` markers to every rendered file.
4. **`agentforge upgrade`** via `copier update` + lock refresh + 3-way merge dry-run output.
5. **`agentforge fork`/`unfork`/`status`** — strip/restore markers; status shows managed/forked/drifted by walking the lock.
6. **Docs + Runbook + CHANGELOG + roadmap + forward-ref sweep + PR**.

## TODO

- [x] User approved Option A.
- [ ] Chunks 1-6.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/features/feat-011-scaffolding-and-upgrade.md`
