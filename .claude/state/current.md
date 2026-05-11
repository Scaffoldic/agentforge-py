---
feature: feat-010-module-discovery
state: implementing
branch: feat/010-module-discovery
started_at: 2026-05-11T18:30
last_milestone_at: 2026-05-11T18:30
last_shipped: feat-009 (Observability — OTel only) shipped via PR #15 @ cd6ec09
blocker: null
flags_for_user: []
---

## Active feature

[`feat-010 — Module discovery & resolution`](../../docs/features/feat-010-module-discovery-and-cli.md)

Deps: feat-001 ✓. (Spec says feat-012 too, but only for the
destructive CLI commands — see scope below.)

User decision (2026-05-11): single PR, **Option B** scope —
runtime side + read-only `list` CLI only. The destructive CLI
commands (`add` / `swap` / `remove`) have a hard dep on feat-012
(Configuration system) for manifest application + config-schema
validation, so they're deferred to a follow-up sub-feat that
lands alongside / right after feat-012.

## Scope (in / out)

In:

| Piece | Where |
|---|---|
| **`importlib.metadata.entry_points()` discovery** | `agentforge-core/resolver/discover.py` (new) |
| Scan `agentforge.*` groups on first use; cache | inside discover module |
| Invalidate cache on `Resolver.clear()` | resolver |
| **`ModuleInfo`** frozen value type | core values |
| **`Resolver.list_installed(category=None)`** | resolver |
| **CLI entry point `agentforge`** | `agentforge/__main__.py` or `agentforge/cli/` |
| **`agentforge list modules`** command | CLI |
| Console-scripts entry-point registration | `agentforge` pyproject.toml |

Out (deferred):

- `Resolver.list_available()` (queries PyPI — complex, low-value).
- `agentforge add module X` (needs feat-012's manifest schema).
- `agentforge swap`, `agentforge remove`.
- Manifest format spec (lives alongside feat-012).

## Chunks (3 total)

1. **Entry-point discovery + `ModuleInfo` + `list_installed`.**
   - New `agentforge_core/values/module.py` with `ModuleInfo`.
   - New `agentforge_core/resolver/discover.py` with
     `discover_entry_points(force=False)` — scans all groups
     starting with `agentforge.` and registers each
     `category=group_suffix, name=ep.name, cls=ep.load()` on the
     global resolver. Caches the scan; `force=True` re-scans.
   - `Resolver.list_installed(category=None) -> list[ModuleInfo]`
     — returns the registered modules with their source
     package + version (from `importlib.metadata`).
   - Auto-trigger discovery on first `Resolver.resolve()` call so
     existing flows pick up entry-point-registered modules
     transparently.
   - Tests: discovery happy path (fake distribution registered
     in-process), missing entry-point → no surprise (just absent),
     conflict (two packages register same name) → clean error,
     list_installed by category + globally.

2. **`agentforge` CLI scaffolding + `list modules` command.**
   - New `agentforge/cli/__init__.py` + `cli/main.py` + `cli/list_modules.py`.
   - Top-level entry point via `[project.scripts]` in `agentforge`'s
     pyproject.toml: `agentforge = "agentforge.cli.main:main"`.
   - argparse-based (no Click / Typer dep). Subcommand: `list
     modules [--category <cat>]`.
   - Output: column-formatted table grouped by category.
   - Tests: CLI invocation via `subprocess` against the entry
     point + direct call to `main(argv)` for parsing.

3. **Docs + PR.** Implementation status + Runbook + CHANGELOG +
   roadmap + forward-ref sweep + PR. Document that
   `add/swap/remove` are deferred and where they will land.

## TODO

- [x] User approves scope (single PR, Option B).
- [ ] Chunk 1.
- [ ] Chunk 2.
- [ ] Chunk 3.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/features/feat-010-module-discovery-and-cli.md`
