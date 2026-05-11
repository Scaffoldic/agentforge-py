---
feature: feat-012-configuration-system
state: implementing
branch: feat/012-configuration-system
started_at: 2026-05-11T20:00
last_milestone_at: 2026-05-11T20:00
last_shipped: feat-010 (Module discovery, read-only) shipped via PR #16 @ bbba56c
blocker: null
flags_for_user: []
---

## Active feature

[`feat-012 — Configuration system`](../../docs/features/feat-012-configuration-system.md)

Deps: feat-001 ✓. User chose **Option A — full scope**: widened
schema + module-side schema integration + layered files + dotted
overrides + env shortcuts + `config validate/show/schema` CLI.

## Already shipped (feat-001 partial)

| Piece | Status |
|---|---|
| `AgentForgeConfig` (minimal: agent + logging) | ✓ |
| `AgentConfig` (flat `budget_usd`) | ✓ |
| `LoggingConfig` (level + run_id_filter + format) | ✓ |
| `load_config(path)` + env-var interpolation (`${VAR}`, `${VAR:default}`, `${VAR:?error}`, `$$`) | ✓ |

## In scope for this PR

| Piece | Where |
|---|---|
| **Widened schema** — `BudgetConfig` (replaces flat `budget_usd`), `ModulesConfig`, `ProvidersConfig`, `OutputConfig`, evaluators / observability sub-shapes | `agentforge_core/config/` (move from `agentforge.config` per spec §4.2) |
| Move config schema + loader from `agentforge` → `agentforge-core` | so the resolver/discovery layer can compose schemas |
| **`system_prompt_file: Path`** support | schema + loader |
| **Module-side schema integration** — modules declare `config_schema: ClassVar[type[BaseModel] \| None]`; loader validates each `modules.<cat>.config` block against the resolved class's schema | resolver + loader |
| **Layered env files** — `agentforge.<env>.yaml` overlays on `agentforge.yaml` (deep merge) via `AGENTFORGE_ENV` | loader |
| **Dotted-path overrides** — `--override agent.budget.usd=10` (CLI) + `overrides=[...]` (loader API) | loader + CLI |
| **`AGENTFORGE_CONFIG`** + **`AGENTFORGE_LOG_LEVEL`** env shortcuts | loader |
| **CLI `agentforge config validate`** | cli |
| **CLI `agentforge config show [--resolved]`** | cli |
| **CLI `agentforge config schema`** (JSON Schema export) | cli |

## Design decisions

- **Schema lives in `agentforge-core`** (moved from `agentforge`). The spec §4.2 calls for it; this lets the resolver compose module schemas without depending on the runtime package. `agentforge.config` re-exports for back-compat.
- **`BudgetConfig`** replaces flat `budget_usd` in the YAML. The `Agent(budget_usd=, max_iterations=)` kwargs remain (locked surface per feat-001) — they continue to drive the runtime `BudgetPolicy`; the YAML simply has a richer shape.
- **Module schema convention**: `class.config_schema: ClassVar[type[BaseModel] | None] = None`. Validator reads it via `getattr`. Optional — modules without one accept any dict.
- **Deep merge for layered files**: dict-of-dicts deep merge; lists replace wholesale (no append). Documented.
- **Dotted-path overrides**: parsed via `path.split(".")`; integer-string segments stay strings (no list indexing for now — keep it simple).
- **CLI `config schema`**: emits Pydantic v2's `model_json_schema()` for the root model. Useful for IDE YAML completion via SchemaStore-style configs.

## Proposed chunks (10 total)

1. **Move schema + loader from `agentforge` to `agentforge-core`.** Re-export from `agentforge.config` for backwards compat. No surface change. Updates Agent's import.
2. **Widened schema**: `BudgetConfig`, `ModulesConfig` with `memory` / `graph` / `retriever` / `evaluators` / `observability` / `tools` / `protocols` sub-fields; `ProvidersConfig` (named registry); `OutputConfig`. Replace flat `budget_usd` with `budget: BudgetConfig`.
3. **`system_prompt_file: Path`** field + loader logic to read it when present.
4. **Layered env files** — `_load_layered(path, env)`; deep-merge helper.
5. **Dotted-path overrides** — `parse_overrides(["a.b=10", ...])` → nested dict; merged after env vars.
6. **`AGENTFORGE_CONFIG` + `AGENTFORGE_LOG_LEVEL` env shortcuts** in `load_config`.
7. **Module-side schema integration** — `cls.config_schema` convention; loader walks `modules.*` blocks, resolves each entry's class, validates the `config` dict against the class's schema.
8. **CLI `agentforge config validate`** — load + report errors with YAML paths.
9. **CLI `agentforge config show [--resolved]`** — pretty-print as YAML; `--resolved` interpolates env vars + overrides.
10. **CLI `agentforge config schema`** — emit JSON Schema for `AgentForgeConfig`.
11. **Docs + Runbook + sweep + PR.** (Numbered 11 — let me call this chunk 11.)

Actually 11 chunks. The line count for this single PR will be substantial; chunking is for reviewability, not gating.

## TODO

- [x] User approves scope (single PR, Option A — full).
- [ ] Chunks 1-11 implementation.
- [ ] PR.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/features/feat-012-configuration-system.md`
