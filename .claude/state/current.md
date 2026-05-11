---
feature: feat-012-configuration-system
state: pre-pr
branch: feat/012-configuration-system
started_at: 2026-05-11T20:00
last_milestone_at: 2026-05-11T21:30
last_shipped: feat-010 (Module discovery, read-only CLI) shipped via PR #16 @ bbba56c
blocker: null
flags_for_user: []
---

## Active feature

[`feat-012 — Configuration system`](../../docs/features/feat-012-configuration-system.md)

All 11 chunks landed. Ready to push + raise PR.

## Chunks shipped

| Chunk | Commit | Scope |
|---|---|---|
| 1-6 | `6a847b8` | Schema moved to `agentforge-core.config`; widened root schema (`BudgetConfig` replaces flat `budget_usd`, `ModulesConfig`, `ProvidersConfig`, `OutputConfig`); `system_prompt_file`; layered env files; dotted-path overrides; `AGENTFORGE_CONFIG` / `AGENTFORGE_LOG_LEVEL` env shortcuts. |
| 7 | `c0d177a` | Module-side schema integration — `cls.config_schema` convention + `validate_module_configs(cfg, strict=)`. |
| 8-10 | `c088273` | `agentforge config validate/show/schema` CLI. |
| 11 | (this commit) | Implementation status + Runbook + CHANGELOG + roadmap + forward-ref sweep. |

## Scope decision recap

User chose **Option A — full scope** for feat-012 (target version
0.1, foundational). Everything from spec §4 lands except:
- Evaluator string-shorthand normalisation (`- faithfulness` →
  `EvaluatorEntry(name=...)`) — small loader follow-up.
- Auto-wiring `modules.*` blocks into `Agent.__init__` — small
  Agent-level follow-up; will ship alongside the destructive CLI
  half of feat-010 (`agentforge add module`).

## Forward-reference sweep (per AGENTS.md rule)

- `docs/features/README.md`: feat-012 row `proposed` → `shipped
  (Python)`.
- `docs/features/feat-001-core-contracts-and-agent.md`: §4.5 "Full
  schema specified in feat-012" rewritten; Runbook "full schema
  ships with feat-012" replaced with what's now live.
- `docs/features/feat-003-llm-provider-abstraction.md`: caching
  Runbook entry rewritten — `llm_options` is in the schema now,
  Agent-level wiring is a small follow-up.
- `docs/features/feat-004-tools-system.md`: "Config integration
  (`agentforge.yaml > agent.tools`): feat-012 lands separately"
  rewritten — schema + resolver are done.
- `docs/features/feat-006-evaluators-and-benchmarks.md`:
  "Configuration loading of evaluators from agentforge.yaml —
  feat-012" rewritten; folded into the auto-wiring follow-up
  note.

Unshipped specs (feat-011, feat-016, feat-017) reference feat-012
in design / dep sections — their own ship-time PRs will refresh
forward-tense language per the AGENTS.md rule.

## Pre-commit gate

Every chunk's commit passed the full gate (ruff format + check,
mypy --strict, bandit, pytest unit + integration, coverage ≥ 90%).

## Next after this PR merges

1. Sync `main`, delete `feat/012-configuration-system` local +
   remote.
2. Next eligible per pipeline §1: lowest-numbered proposed with
   deps shipped:
   - **feat-011 (Scaffolding & upgrade)** — deps feat-010 ✓.
     Now that feat-012 has shipped manifest format + config
     schema integration, feat-011's manifest-based scaffolding
     finally has its real dep met. **feat-011 is now the natural
     next pick.**
   - Or: do the **feat-010 destructive-CLI sub-feat first**
     (deferred from feat-010 PR #16) — `agentforge add module`,
     `swap`, `remove`. This unblocks feat-011's "scaffold a new
     agent" workflow which uses the same manifest-apply machinery.

   Pragmatic order: feat-010-destructive sub-feat first (small,
   uses what feat-012 just shipped), then feat-011 which builds
   on it. Worth flagging to the user.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. After merge: choose between
   `docs/features/feat-010-module-discovery-and-cli.md` (for the
   destructive-CLI follow-up) or
   `docs/features/feat-011-scaffolding-and-upgrade.md`.
