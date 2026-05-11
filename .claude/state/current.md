---
feature: feat-006-evaluators-and-benchmarks
state: pre-pr
branch: feat/006-evaluators-and-benchmarks
started_at: 2026-05-11T13:30
last_milestone_at: 2026-05-11T16:00
last_shipped: feat-008 (Findings & output shapes) shipped via PR #13 @ 670977d
blocker: null
flags_for_user: []
---

## Active feature

[`feat-006 — Evaluators & benchmarks`](../../docs/features/feat-006-evaluators-and-benchmarks.md)

All 8 chunks landed locally. Ready to push + raise PR.

## Chunks shipped

| Chunk | Commit | Scope |
|---|---|---|
| 1 | `87bd0f2` | `RunResult.eval_scores` field + `Agent._run_evaluators` (budget-gated, WARN logging, order-preserving). |
| 2 | `93b241a` | `Coverage` deterministic grader. |
| 3 | `6938866` | `FormatCompliance` deterministic grader. |
| 4 | `3bad0bd` | `RegressionVsBaseline` deterministic grader. |
| 5 | `8689b44` | `Consistency` deterministic grader. |
| 6+7 | `f771791` | `agentforge-eval-geval` package — `GEval` engine + 6 named graders + 6 YAML rubrics + workspace/CI lockstep. |
| 8 | (this commit) | Implementation status + Runbook + CHANGELOG + roadmap + forward-ref sweep + README catalogue + feat-002 runbook update. |

## Forward-reference sweep (per AGENTS.md rule)

`git grep -nE 'feat-006|agentforge-eval-geval|Correctness|...' docs/features/*.md`:

- `docs/features/README.md`: feat-006 status `proposed` → `shipped
  (Python)`.
- `docs/features/feat-002-reasoning-strategies.md`: two updates —
  the Implementation status section's ToT scorer note (line 413)
  and the Runbook section's ToT scorer note (line 523). Both
  previously said "until feat-006 lands the full eval framework";
  rewritten to acknowledge feat-006 has shipped the post-run
  evaluator surface while ToT's *in-strategy* `scorer="judge"`
  still calls `Agent.model` (a small follow-up to wire the named-
  provider config).
- Unshipped specs (`feat-012`, `feat-017`, `feat-018`) reference
  feat-006 in design / risks sections — their own PRs will refresh
  forward-tense language at ship time per the AGENTS.md rule.
- `feat-008` and `feat-001` references are dependency declarations,
  not forward-tense.

## Pre-commit gate

All 8 chunks went through the local gate with all hooks green
(ruff format + check, mypy --strict, bandit, pytest unit +
integration, coverage ≥ 90%).

## Next after this PR merges

1. Sync `main`, delete `feat/006-evaluators-and-benchmarks` local +
   remote.
2. Next eligible per pipeline §1: lowest-numbered proposed feature
   with deps shipped. After feat-006:
   - **feat-009** (Observability) — deps feat-001 ✓ + feat-007 ✓.
   - feat-010 (Module discovery & CLI) — deps feat-001 ✓.
   - feat-011 (Scaffolding & upgrade) — deps feat-001 ✓.
   - feat-012 (Configuration system) — deps feat-001 ✓.

   feat-009 wins by lowest number.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. After this PR merges: `docs/features/feat-009-observability.md`
