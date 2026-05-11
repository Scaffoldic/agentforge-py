---
feature: feat-006-evaluators-and-benchmarks
state: implementing
branch: feat/006-evaluators-and-benchmarks
started_at: 2026-05-11T13:30
last_milestone_at: 2026-05-11T13:30
last_shipped: feat-008 (Findings & output shapes) shipped via PR #13 @ 670977d
blocker: null
flags_for_user: []
---

## Active feature

[`feat-006 — Evaluators & benchmarks`](../../docs/features/feat-006-evaluators-and-benchmarks.md)

Deps: feat-001 ✓ (Evaluator ABC + EvalResult), feat-003 ✓ (Bedrock
provider for judge), feat-008 ✓ (Finding shape).

User decision (2026-05-11): **single PR** for the entire feature,
even though it crosses two packages (`agentforge` + new
`agentforge-eval-geval`).

## Scope

Already shipped (feat-001):

| Piece | Status |
|---|---|
| `Evaluator` ABC at `agentforge_core/contracts/evaluator.py` | ✓ |
| `EvalResult` frozen value type | ✓ |
| `Agent(evaluators=[...])` constructor kwarg | ✓ (accepts list; not wired) |

This PR ships:

| Piece | Where |
|---|---|
| **`RunResult.eval_scores: tuple[EvalResult, ...]`** field | `agentforge-core/values/state.py` |
| **`Agent.run()` evaluator loop** — after strategy, before `on_finish`, with budget gating | `agentforge/agent.py` |
| **`coverage`** deterministic grader (fraction of expected items found vs reference) | `agentforge/eval/coverage.py` |
| **`format_compliance`** deterministic grader (JSON schema / regex / grammar) | `agentforge/eval/format_compliance.py` |
| **`regression_vs_baseline`** deterministic grader (string / structural diff vs baseline file) | `agentforge/eval/regression.py` |
| **`consistency`** deterministic grader — re-runs the agent N times, scores agreement | `agentforge/eval/consistency.py` |
| **String resolution** `Agent(evaluators=["coverage", ...])` via resolver | `agentforge/resolver_register.py` |
| **`agentforge-eval-geval`** new workspace package | `packages/agentforge-eval-geval/` |
| G-Eval engine — caller-supplied or named rubric, uses a separate judge `LLMClient` | inside new package |
| 6 named judge graders: `correctness`, `faithfulness`, `groundedness`, `hallucination`, `relevance`, `helpfulness` | inside new package |
| Rubric YAML files (one per named grader) | `packages/agentforge-eval-geval/rubrics/` |
| Entry-point registration (`agentforge.evaluators.correctness = ...`) | new package's `pyproject.toml` |

## Design choices

- **`RunResult.eval_scores` as `tuple[EvalResult, ...]`** not `dict`.
  Spec example shows a dict in the README-friendly description but
  the ABC already returns full `EvalResult` objects; a tuple lets
  callers index by name (`{r.evaluator: r for r in result.eval_scores}`)
  and preserves order — which matters when the same rubric is run
  multiple times. Frozen tuple matches the rest of `RunResult`.

- **Evaluator's `finding` parameter receives the `RunResult`.** The
  ABC has `finding: Any` and the spec's example evaluators
  (`coverage`, `faithfulness`, `regression`) operate on the
  *whole run output*, not on a single `Finding`. Pass `RunResult`
  as `finding`, bundle `task`, `agent_id`, `state` into `context`.
  Documented; doesn't change the locked ABC signature.

- **Budget gating**: skip evaluator if
  `budget.remaining_usd < evaluator.cost_estimate_usd`. Log at
  WARN. Skipped evaluators do not appear in `eval_scores`.

- **`consistency` grader** re-runs the agent N times. Implementation:
  the grader accepts the `task` from `context`, calls a caller-
  supplied factory `agent_factory: Callable[[], Agent]` to build a
  fresh agent (avoids reentrancy of the same instance), tracks
  agreement on `RunResult.output`. Costs of the re-runs charge to
  the **outer** agent's budget (passed through). Defaults `n=3`.

- **`agentforge-eval-geval` package** mirrors `agentforge-bedrock`
  / `agentforge-memory-sqlite` layout: own `pyproject.toml`,
  `src/agentforge_eval_geval/`, `tests/unit/`. Entry points
  register the named graders. Cross-region judge providers via
  the existing resolver (`Agent(judge_provider="bedrock:...")`).

- **Judge provider plumbing**: each judge grader takes
  `judge_provider: str | LLMClient` at construction. String form
  resolves through the resolver same as `Agent(model=...)`.

## Proposed chunks (8 total)

1. **`RunResult.eval_scores` field + Agent.run integration.**
   Add `eval_scores: tuple[EvalResult, ...] = ()` to RunResult.
   Wire `Agent.run()` to iterate `self._evaluators` after the
   strategy returns and before `on_finish`, with budget gating.
   Unit tests: hook fires with eval results; budget-exhausted
   evaluators are skipped + logged; eval order preserved.

2. **`coverage` deterministic grader.** First concrete grader —
   exercises the resolver registration path.

3. **`format_compliance` deterministic grader.** JSON schema +
   regex + grammar modes.

4. **`regression_vs_baseline` deterministic grader.** Load baseline
   file (JSONL); compute string / structural / semantic-via-
   embedding diff. Semantic mode optional, requires an
   `EmbeddingClient`.

5. **`consistency` deterministic grader.** Recursive agent
   invocation via caller-supplied factory; N-way agreement on
   output. Tests use `FakeLLMClient` to avoid real LLM cost.

6. **`agentforge-eval-geval` package skeleton + G-Eval engine +
   `correctness` rubric.** New workspace member. pyproject.toml
   wired into root workspace deps + CI/pre-commit lockstep.

7. **5 more named judge graders + rubric YAMLs:** `faithfulness`,
   `groundedness`, `hallucination`, `relevance`, `helpfulness`.

8. **Docs + PR.** Implementation status + Runbook + CHANGELOG +
   roadmap + forward-ref sweep + raise PR.

## TODO

- [x] User approves scope (single PR).
- [ ] Chunk 1 — RunResult field + Agent integration.
- [ ] Chunks 2–5 — deterministic graders.
- [ ] Chunks 6–7 — geval package + 6 judge graders.
- [ ] Chunk 8 — docs + PR.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/features/feat-006-evaluators-and-benchmarks.md`
