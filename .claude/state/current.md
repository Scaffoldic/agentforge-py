---
feature: feat-008-findings-and-output-shapes
state: pre-pr
branch: feat/008-findings-and-output-shapes
started_at: 2026-05-11T11:30
last_milestone_at: 2026-05-11T13:00
last_shipped: chore/backfill-runbooks shipped via PR #12 @ b173d31
blocker: null
flags_for_user: []
---

## Active feature

[`feat-008 — Findings & output shapes`](../../docs/features/feat-008-findings-and-output-shapes.md)

All four chunks landed. Ready to push + raise PR.

## Chunks shipped

| Chunk | Commit | Scope |
|---|---|---|
| 1 | `bfb8c33` | Variants (Simple/Patch/Narrative/MultiSpan) + helpers (Patch, Span) as frozen Pydantic v2 models in `agentforge.findings`. 19 unit tests covering Protocol conformance, frozen-ness, JSON round-trip, field validation. |
| 2 | `4f5e95c` | `FindingRenderer` ABC in `agentforge-core/contracts/renderer.py` + `RendererRegistry` in `agentforge/renderers/registry.py` (most-specific-wins dispatch, `MissingRendererError`). 9 unit tests. |
| 3 | `26b5da7` | Four built-in renderers (`ScorecardRenderer`, `PatchApplierRenderer`, `MarkdownRenderer`, `SpanTableRenderer`) + `RendererRegistry.default()` factory. 21 unit tests covering text + markdown output, format / variant rejection, `supports()` semantics, end-to-end dispatch, in-place override. |
| 4 | (this commit) | Implementation status + Runbook + CHANGELOG entry + roadmap move (backlog → shipped) + feat-008 forward-reference sweep across runbooks + README catalogue status update. |

## Forward-reference sweep (per AGENTS.md rule from PR #12)

`git grep -nE 'feat-008|SimpleFinding|PatchFinding|...' docs/features/*.md`
audited:

- `docs/features/README.md` line 42: feat-008 status updated
  `proposed` → `shipped (Python)`.
- `docs/features/feat-005-persistence-and-memory.md` §4.1 line 77-91:
  example imports `SimpleFinding` and uses `Claim.from_finding(...)`.
  `SimpleFinding` is now real — example is no longer aspirational
  for that line. `Claim.from_finding` is still not implemented;
  that's a feat-005 follow-up, not feat-008's responsibility.
- `docs/features/feat-005-persistence-and-memory.md` line 233, 254:
  reference-section mentions of feat-008 — already correctly
  describe the dependency direction. No changes.
- `docs/features/feat-006/014/015/016`: dependency declarations on
  feat-008. Those features are still unshipped; their existing
  `Finding` / `SimpleFinding` example code now points to real types.
  No textual updates needed — when those features ship, their own
  PRs will fix any forward-tense language in their own Runbook
  sections (per the policy in AGENTS.md).

## Pre-commit gate

All four chunks went through the local gate with all hooks green
(ruff format + check, mypy --strict, bandit, pytest unit +
integration, coverage ≥ 90%).

## Next after this PR merges

1. Sync `main`, delete `feat/008-findings-and-output-shapes` local
   + remote.
2. Next eligible per pipeline §1: lowest-numbered proposed feature
   with deps shipped. After feat-008 ships, the eligible set is:
   - **feat-006** (Evaluators) — deps feat-001 ✓ + feat-003 ✓ +
     feat-008 ✓ now.
   - **feat-009** (Observability) — deps feat-001 ✓ + feat-007 ✓.
   - feat-010 (Module discovery & CLI) — deps feat-001 ✓.
   - feat-011 (Scaffolding & upgrade) — deps feat-001 ✓.
   - feat-012 (Configuration system) — deps feat-001 ✓.

   feat-006 wins by lowest number.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. After this PR merges: `docs/features/feat-006-evaluators-and-benchmarks.md`
