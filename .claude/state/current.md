---
feature: feat-010-module-discovery
state: pre-pr
branch: feat/010-module-discovery
started_at: 2026-05-11T18:30
last_milestone_at: 2026-05-11T19:30
last_shipped: feat-009 (Observability — OTel only) shipped via PR #15 @ cd6ec09
blocker: null
flags_for_user: []
---

## Active feature

[`feat-010 — Module discovery & resolution`](../../docs/features/feat-010-module-discovery-and-cli.md)

All 3 chunks landed. Ready to push + raise PR.

## Chunks shipped

| Chunk | Commit | Scope |
|---|---|---|
| 1 | `ece4195` | Entry-point discovery + `ModuleInfo` + `Resolver.list_installed`. |
| 2 | `409067e` | `agentforge` CLI scaffold + `list modules` (text + JSON). |
| 3 | (this commit) | Implementation status + Runbook + CHANGELOG + roadmap + forward-ref sweep. |

## Scope decision recap

Option B (single PR, runtime + read-only `list` CLI). Destructive
CLI (`add`, `swap`, `remove`) depends on feat-012 — deferred to a
follow-up sub-feat. `Resolver.list_available()` (PyPI query) also
deferred. Documented in:
- `docs/roadmap.md` new "feat-010 destructive-CLI sub-feat" section.
- `docs/features/README.md` catalogue row.
- `feat-010` spec's Implementation status + Runbook.

## Forward-reference sweep (per AGENTS.md rule)

- `docs/features/README.md` — feat-010 status updated.
- `docs/features/feat-003-llm-provider-abstraction.md` — custom-
  provider runbook rewritten: feat-010 has now shipped auto-load.
- `docs/features/feat-004-tools-system.md` — "Entry-point auto-
  loading of third-party tool packages — that's feat-010" moved
  out of "What's not yet implemented".
- `docs/features/feat-006-evaluators-and-benchmarks.md` —
  "String-name resolution... needs feat-010" reworded.

Unshipped specs (feat-011, feat-013, feat-017) reference feat-010
in dependency declarations — those features' own ship-time PRs
will refresh forward-tense language per the AGENTS.md rule.

## Pre-commit gate

Each chunk's commit passed the full gate (ruff format + check,
mypy --strict, bandit, pytest unit + integration, coverage ≥ 90%).

## Next after this PR merges

1. Sync `main`, delete `feat/010-module-discovery` local + remote.
2. Next eligible per pipeline §1: lowest-numbered proposed with
   deps shipped. After feat-010:
   - **feat-011** (Scaffolding & upgrade) — deps feat-010 ✓.
   - feat-012 (Configuration system) — deps feat-001 ✓.

   feat-011 wins by lowest number, but it specifically needs the
   destructive CLI / manifest format from feat-010 which is
   deferred — so feat-012 is the realistic next pick to unblock
   the rest. **Worth flagging to the user when they pick up.**

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. After merge: `docs/features/feat-012-configuration-system.md`
   (next realistic feature given the feat-011 dep on the deferred
   CLI half of feat-010).
