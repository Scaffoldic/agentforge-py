---
feature: chore/backfill-runbooks
state: pr-pending
branch: chore/backfill-runbooks
started_at: 2026-05-11T10:00
last_milestone_at: 2026-05-11T10:30
last_shipped: feat-007 (Production rails — FallbackChain) shipped via PR #11 @ f61ad44
blocker: null
flags_for_user: []
---

## Active task

Retroactive backfill of the `## Runbook` policy locked in
mid-feat-007. Adds task-oriented runbook sections to the five
already-shipped feature specs (feat-001 / feat-002 / feat-003 /
feat-004 / feat-005). Also fixes a stale `Agent(budget=...)`
example in feat-007's runbook — the Agent constructor takes
`budget_usd=` and `max_iterations=`, not a `budget=` kwarg.

## What changed

- `docs/features/feat-001-core-contracts-and-agent.md` — Runbook
  section: minimum agent, budget caps, step trace, hooks, config,
  provider switching, sync shim, when-not-to-use.
- `docs/features/feat-002-reasoning-strategies.md` — Runbook
  section: picking a strategy, tuning ReAct / Plan-Execute / ToT
  (judge scorer) / MultiAgentSupervisor, step inspection.
- `docs/features/feat-003-llm-provider-abstraction.md` — Runbook
  section: pointing at Bedrock, cross-region inference profiles,
  caching / thinking, embeddings, cost accounting, custom-provider
  registration.
- `docs/features/feat-004-tools-system.md` — Runbook section:
  attaching tools, `@tool` decorator, locking down `shell` /
  `file_read`, `FakeTool` for tests, timeouts, step inspection.
- `docs/features/feat-005-persistence-and-memory.md` — Runbook
  section: backend picker, sqlite / postgres / neo4j / surrealdb
  setup, RAG via `Retriever`, namespacing, `init_schema()`, live
  integration tests.
- `docs/features/feat-007-production-rails.md` — fixed
  `Agent(budget=BudgetPolicy(...))` example to use the real
  kwargs `budget_usd=` + `max_iterations=`.
- `CHANGELOG.md` — `[Unreleased] / Docs` entry summarising the
  backfill + the feat-007 fix.

## Pre-commit gate

All hooks green at the time of commit (ruff format + check, mypy
strict, bandit, pytest unit + integration, coverage ≥ 90%).
Doc-only changes touched no code, so the gate was a confirmation
rather than a real probe.

## Next after this PR merges

1. Sync `main`, delete `chore/backfill-runbooks` local + remote.
2. Move to **feat-008 (Findings & output shapes)** per pipeline §1
   — lowest-numbered proposed feature with deps shipped
   (feat-001 ✓). Spec is `docs/features/feat-008-findings-and-output-shapes.md`.
3. Open `feat/008-findings-and-output-shapes` branch and follow
   the standard pre-feature checklist (read spec end-to-end, draft
   chunk plan in state, get user approval, implement).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. After this PR merges: `docs/features/feat-008-findings-and-output-shapes.md`
