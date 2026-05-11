---
feature: feat-009-observability
state: pre-pr
branch: feat/009-observability
started_at: 2026-05-11T16:30
last_milestone_at: 2026-05-11T18:00
last_shipped: feat-006 (Evaluators) shipped via PR #14 @ 09ab1cf
blocker: null
flags_for_user: []
---

## Active feature

[`feat-009 — Observability`](../../docs/features/feat-009-observability.md)

All 7 chunks landed locally. Ready to push + raise PR.

## Chunks shipped

| Chunk | Commit | Scope |
|---|---|---|
| 1 | `d369dc2` | Hook fan-out + on_step wiring + error isolation. |
| 2 | `ccee40d` | JSON log format (`JsonFormatter`, install/uninstall, Agent wiring). |
| 3-6 | `7901253` | OTel tracing in core (api dep, `get_tracer`) + `agent.run` root span instrumentation in Agent.run + new `agentforge-otel` workspace package (`OpenTelemetryHook`). |
| 7 | (this commit) | Implementation status + Runbook + CHANGELOG + roadmap + forward-ref sweep. |

## Scope decision recap

User chose Option B (single PR, OTel only). Vendor packages
(`agentforge-langfuse`, `-phoenix`, `-evidently`, `-statsd`)
deferred to follow-up sub-feats. Documented as such in:
- `docs/roadmap.md` new "feat-009 vendor-package sub-feats" section.
- `docs/features/README.md` catalogue row.
- `feat-009` spec's Implementation status + Runbook ("Which vendor
  can ingest these traces?").

## Forward-reference sweep (per AGENTS.md rule)

- `docs/features/README.md`: feat-009 status `proposed` → `shipped
  (Python, OTel only)`; module package list updated.
- `docs/features/feat-004-tools-system.md`: "Cost attribution per
  tool — feat-009 (Observability)" moved out of "what's not yet"
  list; replaced with a note that feat-009 has shipped tool-call
  attribution via the OTel hook.
- `docs/features/feat-007-production-rails.md` references feat-009
  in "Blocks" — design-section dependency declaration, not
  forward-tense; no change needed.
- Other specs (`feat-014` A2A trace propagation, `feat-018`
  guardrail spans) reference feat-009 in unshipped designs — their
  own ship-time PRs will refresh forward-tense language per the
  AGENTS.md rule.

## Pre-commit gate

Every chunk's commit went through the full local gate (ruff format
+ check, mypy strict, bandit, pytest unit + integration, coverage
≥ 90%) and passed.

## Next after this PR merges

1. Sync `main`, delete `feat/009-observability` local + remote.
2. Next eligible per pipeline §1: lowest-numbered proposed feature
   with deps shipped. After feat-009:
   - **feat-010** (Module discovery & CLI) — deps feat-001 ✓.
   - feat-011 (Scaffolding & upgrade) — deps feat-001 ✓.
   - feat-012 (Configuration system) — deps feat-001 ✓.

   feat-010 wins by lowest number.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. After this PR merges: `docs/features/feat-010-module-discovery-and-cli.md`
