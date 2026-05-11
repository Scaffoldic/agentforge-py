# feat-006: Evaluators & benchmarks

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-006 |
| **Title** | Evaluators — `Evaluator` ABC, built-in graders, LLM-judge |
| **Status** | shipped (Python — `agentforge-py` PR pending merge; TypeScript pending) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.2 |
| **Languages** | both |
| **Module package(s)** | `agentforge` (ABC + 5 built-ins), `agentforge-eval-geval` (LLM-judge), optional adapters for Ragas / DeepEval |
| **Depends on** | feat-001, feat-003, feat-008 |
| **Blocks** | none |

---

## 1. Why this feature

An agent that ships without quality gates ships regressions. The team that
spent two weeks tuning a prompt has no objective way to compare yesterday's
agent to today's, no way to catch when the next model upgrade silently
regresses one in twenty answers, and no way to set a quality bar before
production deploy.

The other failure mode: teams that *do* write evaluators write them as bespoke
test scripts that nobody else can run, that don't integrate with the agent's
runtime cost cap, and that produce numbers nobody trusts because the rubric
isn't versioned.

## 2. Why it must ship as framework

- **A common evaluator interface lets you compare agents.** "This agent scores
  0.84 on faithfulness; this other agent scores 0.71" is only a meaningful
  comparison if both ran the same evaluator with the same definition.
- **LLM-judge cost must respect the run budget.** A judge that calls Claude
  on every output can cost more than the agent itself. Shared `BudgetPolicy`
  (feat-007) accounting requires the judge to run inside the framework
  runtime.
- **Run-id propagation through eval is required for traceability.** Every eval
  result must point back to the run it scored.
- **Reusable graders avoid reinvented wheels.** Faithfulness, groundedness,
  consistency, regression-vs-baseline are well-known patterns. Shipping them
  once means every agent gets them tested by hundreds of users.
- **Without framework ownership:** evals become per-team scripts, the rubric
  never gets versioned, judge costs explode, results aren't comparable.

## 3. How derived agents benefit

- **Plug in a built-in grader in one line.** `evaluators=["faithfulness",
  "consistency"]` in `Agent(...)` — done.
- **LLM-judge with a versioned rubric.** `agentforge-eval-geval` ships rubric
  templates the team curates over time; evolving the rubric is a config edit.
- **Cost-bounded by default.** Judge calls draw from the run's existing
  budget; if the run has $0.50 of budget left, the judge gets at most $0.50.
- **CI integration for free.** `agentforge eval` (feat-017) runs against a
  fixture set, prints a scorecard, fails the CI job below a threshold.
- **Comparable metrics across agents.** Two agents on the same task are
  scorable side-by-side using identical evaluator code.

## 4. Feature specifications

### 4.1 User-facing experience

```python
from agentforge import Agent
from agentforge.eval import Faithfulness, Consistency, RegressionVsBaseline
from agentforge_eval_geval import GEval

agent = Agent(
    model="anthropic:claude-sonnet-4.7",
    tools=[...],
    evaluators=[
        Faithfulness(),
        Consistency(),
        GEval(rubric="correctness"),
        RegressionVsBaseline(baseline_path="./baselines/v0.4.json"),
    ],
)

result = await agent.run("Summarise this PR")
print(result.eval_scores)
# { "faithfulness": 0.91, "consistency": 1.0, "geval.correctness": 0.85,
#   "regression_vs_baseline": "improved" }
```

CLI:

```bash
agentforge eval --fixtures tests/fixtures/golden.jsonl --threshold 0.8
```

### 4.2 Public API / contract

```python
# agentforge_core/contracts/eval.py — locked
class Evaluator(ABC):
    name: str
    cost_estimate_usd: float = 0.0   # 0 for non-LLM, > 0 for judge

    @abstractmethod
    async def evaluate(self, finding: Finding, context: dict[str, Any]) -> EvalResult: ...

class EvalResult(BaseModel):
    evaluator: str
    score: float            # 0..1, NaN if not applicable
    label: str | None       # "pass" | "fail" | "warn" | <custom>
    reasoning: str | None
    raw: dict[str, Any] = {}
```

**Deterministic graders (in `agentforge`, $0 — no LLM call):**

| Name | What it scores |
|---|---|
| `coverage` | Fraction of expected items found vs a reference set |
| `regression_vs_baseline` | Diff vs locked baseline outputs (string / structural / semantic via embedding) |
| `format_compliance` | Output matches a declared JSON schema, regex, or grammar |
| `consistency` | Same input → same output across N samples (re-runs the agent; LLM cost charged to run budget, not to evaluator) |

**LLM-judge graders (in `agentforge-eval-geval`, cost > 0):**

| Name | What it scores |
|---|---|
| `correctness` | Output matches the ground truth answer (rubric-tunable for binary / Likert / ordinal) |
| `faithfulness` | Output is *supported by* the retrieved evidence (no claims that go beyond what was retrieved) |
| `groundedness` | Output *stays inside* the provided sources (no off-source content) |
| `hallucination` | Output contains content not derivable from inputs (faithfulness + groundedness combined into a single risk score, with attribution to the offending span) |
| `relevance` | Output addresses the user's question (vs going off-topic) |
| `helpfulness` | Output is useful — actionable, complete, well-structured |
| `geval` | Generic LLM-judge with caller-supplied rubric (the underlying engine for the named graders above) |

> **Note on the relationship to feat-018 (security guardrails).** PII
> leakage and toxicity overlap two concerns: at output time they are
> *gates* (block / redact in real time — feat-018); as a metric over many
> runs they are *scores* (how often does this agent leak? — this feature).
> Use feat-018 to prevent; use these to measure. Both can run on the same
> agent; the integration tests cover the interaction.

**Optional adapters / additional graders:**

| Module | Provides |
|---|---|
| `agentforge-eval-ragas` | Ragas RAG-quality metrics (context_precision, context_recall, answer_correctness, etc.) |
| `agentforge-eval-deepeval` | DeepEval suite (G-Eval, faithfulness, hallucination, summarisation, bias) |
| `agentforge-eval-toxicity` | Toxicity / bias scoring (Detoxify or moderation-API based) |
| `agentforge-eval-codeexec` | For code-emitting agents — runs generated code in sandbox, scores by test-pass rate |

### 4.3 Internal mechanics

After strategy returns, before `on_finish`:

```
for evaluator in agent.evaluators:
    if budget.remaining_usd >= evaluator.cost_estimate_usd:
        result = await evaluator.evaluate(finding, context)
        agent.state.eval_results.append(result)
    else:
        log.warning(f"skipping {evaluator.name}: budget exhausted")
```

Cost-bounded: if a judge needs $0.20 and the run has $0.05 left, the judge is
skipped (logged) — never silently overspending.

### 4.4 Module packaging

- `agentforge` ships the ABC + 4 deterministic graders (`coverage`,
  `regression_vs_baseline`, `format_compliance`, `consistency`).
- `agentforge-eval-geval` ships the LLM-judge engine plus the 6 named
  judge graders (`correctness`, `faithfulness`, `groundedness`,
  `hallucination`, `relevance`, `helpfulness`) with reference rubrics.
  Rubrics are YAML files inside the package, version-pinned with the
  module, overrideable per agent.
- Adapter modules wrap upstream libraries (Ragas, DeepEval) and expose
  their metrics as `Evaluator` instances. Same registration mechanism;
  same cost-bounded execution.

### 4.5 Configuration

```yaml
agent:
  evaluators:
    # Deterministic — free, run every time
    - "coverage"
    - "format_compliance":
        schema: "./schemas/output.json"

    # LLM-judge — costed, gated by remaining budget
    # judge_provider references a named provider declared in `providers:`
    # (see feat-003). Falls back to eval_options.default_judge_provider.
    - "correctness":
        ground_truth_field: "expected"
        cost_cap_usd: 0.05
        judge_provider: "fast-judge"      # named provider (recommended)
    - "hallucination":
        sources_field: "retrieved_docs"
        cost_cap_usd: 0.05
        # falls back to default_judge_provider below
    - "relevance":
        cost_cap_usd: 0.02
        judge_model: "anthropic:claude-haiku-4-5"   # inline shorthand still works

    # Custom rubric via geval
    - geval:
        name: "code-review-quality"
        rubric_file: "./rubrics/cr-quality.yaml"
        cost_cap_usd: 0.10
        judge_provider: "fast-judge"

  eval_options:
    on_failure: "warn"                      # "warn" | "fail" | "ignore"
    skip_when_budget_below_usd: 0.05
    default_judge_provider: "fast-judge"    # default for any judge that doesn't specify
```

**Why a separate judge provider matters.** The reasoning model that powers
the agent is typically large and expensive (Sonnet, Opus, GPT-4o). Running
the LLM-judge on the same model on every output doubles the cost. A cheap
judge (Haiku, gpt-4o-mini, Gemini Flash) is usually accurate enough for
the rubric, costs a fraction, and is independent of the reasoning model
(reduces "judge agrees with itself" bias). Named providers in feat-003
make the split a config edit, not a code change.

## 5. Plug-and-play & upgrade story

Adding `agentforge-eval-geval` is a `pip install` + module add. New rubrics
ship as YAML files inside the package; the agent picks one by name. Custom
rubrics live alongside the agent's code and reference an explicit path.

Upgrades may add new built-in graders or tighten thresholds; agent's
configured set is opt-in, never automatically expanded.

## 6. Cross-language parity

ABC + EvalResult shape identical. Five built-ins ship in both languages.
G-Eval module Python first; TS at 0.4.

## 7. Test strategy

- **Conformance:** every evaluator passes "honest score" tests — known good
  pairs score high, known bad pairs score low.
- **Cost honesty:** declared `cost_estimate_usd` matches actual.
- **Rubric versioning:** rubric file change requires a version bump; old
  results identifiable by rubric version.
- **Determinism:** non-LLM graders deterministic given same input;
  documented.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| LLM judge is expensive on long runs | Cost cap per call + skip-if-budget-below threshold |
| Judge rubric drift over versions | Rubric pinned to module version; old results stay comparable to results from same version |
| Built-in metrics oversimplified for some domains | They are reference impls; agents can write custom evaluators easily |
| Where does eval *data* (fixtures, baselines) live? | In the agent's repo, not the framework; framework provides loader helpers |
| Streaming eval results during a run vs after | After. Streaming eval interleaves with strategy and complicates cost accounting |

## 9. Out of scope

- A full experiment-tracking system (W&B, MLflow). Eval results are recorded
  in `RunResult`; long-term tracking is the agent's choice.
- Human-in-the-loop labelling UI. Out of scope; integrate with Label Studio
  or similar via tools if needed.
- Classical NLP metrics (BLEU, ROUGE, METEOR). Easy to add as custom
  evaluators; rarely useful for agentic outputs; not shipped by default.
- **Real-time gating.** Evaluators score *after* the run; they do not block.
  For real-time defenses (refuse a tool call, redact PII before output)
  use feat-018 (safety guardrails) — that is the correct primitive.
- **Adversarial / red-team test harnesses** (Garak, PyRIT). Out of scope as
  a framework feature; integrate via `agentforge eval` against a
  red-team fixture set.

## 10. References

- [`architecture.md`](../design/architecture.md) §5
- feat-001, feat-003, feat-008
- Archived: `docs/archive/cr/CR-017*.md`, `docs/archive/subsystem-evaluation.md`
- Prior art: Ragas, DeepEval, G-Eval paper (NG et al. 2023)

---

## Implementation status

**Status: shipped (Python).** Landed across 8 chunks on
`feat/006-evaluators-and-benchmarks`.

| Chunk | Scope |
|---|---|
| 1 | `RunResult.eval_scores: tuple[EvalResult, ...]` field + `Agent.run` evaluator loop (budget-gated, ordered, logs skips at WARN via `agentforge.evaluators` logger). |
| 2 | `Coverage` deterministic grader — fraction of expected items found, default substring match, optional `extractor=` for structured output. |
| 3 | `FormatCompliance` deterministic grader — three modes (`regex=`, `pydantic_model=`, `json_parseable=True`); rejects multi-mode at construction. |
| 4 | `RegressionVsBaseline` deterministic grader — JSONL baseline file, `exact` / `structural` modes, `no_baseline` label with NaN score for unmatched tasks. |
| 5 | `Consistency` deterministic grader — N re-runs via caller-supplied `runner` callable, fraction-of-agreement score, custom `matcher=` for fuzzy compare. |
| 6+7 | `agentforge-eval-geval` package (new workspace member): `GEval` engine + 6 named graders (`Correctness`, `Faithfulness`, `Groundedness`, `Hallucination`, `Relevance`, `Helpfulness`) + 6 versioned YAML rubrics shipped inside the package + entry-point registration under `agentforge.evaluators`. |
| 8 | This Implementation section + Runbook + CHANGELOG + roadmap + forward-reference sweep. |

### Deviations from this spec

- **`Agent(evaluators=[...])` plumbing.** The constructor kwarg
  shipped under feat-001 but `Agent.run()` never iterated the list.
  This PR closes the gap. Evaluators receive the `RunResult` as
  `finding` (the spec's signature allowed `Any`) and a `context`
  dict carrying `task`, `state`, `budget`.
- **`RunResult.eval_scores` is a `tuple[EvalResult, ...]`, not a
  dict.** Spec §4.1's example showed a flat dict; the tuple preserves
  configured order (which matters when the same rubric runs more than
  once with different inputs) and matches the rest of `RunResult`'s
  frozen-tuple convention. Callers index by name via
  `{r.evaluator: r for r in result.eval_scores}`.
- **`format_compliance` ships three modes (`regex`, `pydantic_model`,
  `json_parseable`)**, not the spec's "JSON schema, regex, grammar"
  triple. JSON-Schema-Draft validation would add the `jsonschema`
  dependency; Pydantic v2 covers schema enforcement using a
  dependency the project already takes. Grammar mode (Lark / ANTLR)
  is deferred.
- **`regression_vs_baseline`** ships `exact` and `structural` modes
  only. Semantic-via-embedding mode is deferred — would require an
  `EmbeddingClient` dependency.
- **`consistency`** uses a caller-supplied
  `runner: Callable[[str], Awaitable[Any]]` rather than auto-
  constructing a new `Agent`. Keeps the grader usable with arbitrary
  re-execution strategies (different seed, different judge,
  re-prompted, etc.) and avoids the reentrancy hazard of calling
  `self.run()` from inside the run.
- **G-Eval cost accounting.** Judge call cost is committed to the
  run's `BudgetPolicy` via `contextlib.suppress(Exception)` — failure
  to commit (e.g. cap exceeded mid-run) does not void the
  `EvalResult`, since the score is still informative. The skip-gate
  on `evaluator.cost_estimate_usd` is the primary cap enforcement.
- **No `agentforge eval` CLI** (the spec's §3 mentions
  `agentforge eval --fixtures ... --threshold 0.8`). CLI tooling
  lives in feat-017; this PR ships only the runtime side.

### What's *not* yet implemented

- **`agentforge eval` CLI** + fixture-runner — feat-017.
- **Configuration loading** of evaluators from `agentforge.yaml`
  (`agent.evaluators: ["faithfulness", ...]`) — feat-012.
- **String-name resolution at the Agent constructor**: today,
  agents pass constructed grader instances
  (`Agent(evaluators=[Coverage(reference={...})])`). feat-010 has
  shipped the resolver's entry-point discovery, so the named
  graders are findable via `Resolver.resolve("evaluators",
  "coverage")` — wiring `Agent(evaluators=["coverage", ...])` to
  go through the resolver is a small Agent-level follow-up; the
  resolver work itself is done.
- **`agentforge-eval-ragas`**, **`agentforge-eval-deepeval`**,
  **`agentforge-eval-toxicity`**, **`agentforge-eval-codeexec`**
  adapter packages.
- **Tree-of-Thoughts `scorer="judge"` rewiring** to use a separate
  judge provider — still uses `Agent.model` (same model, separate
  calls). Documented in feat-002's runbook update.
- **TypeScript port** of the whole feat-006 surface.

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented "how do I…" content. This is the canonical
home for the feature's runbook; feat-011 / feat-019 consume these
sections into scaffolded agent projects.

### How do I add evaluators to an agent?

Pass constructed grader instances to `Agent(evaluators=[...])`:

```python
from agentforge import Agent
from agentforge.eval import Coverage, FormatCompliance
from agentforge_bedrock import BedrockClient
from agentforge_eval_geval import Correctness, Faithfulness

judge = BedrockClient(model_id="us.anthropic.claude-haiku-4-5")

agent = Agent(
    model="bedrock:us.anthropic.claude-sonnet-4-5-20250929",
    evaluators=[
        Coverage(reference={"alpha", "beta", "gamma"}),
        FormatCompliance(pydantic_model=MyAnswerSchema),
        Correctness(judge=judge, ground_truth_field="expected"),
        Faithfulness(judge=judge, sources_field="retrieved_docs"),
    ],
    budget_usd=2.0,
)

result = await agent.run("Summarise this PR")
for r in result.eval_scores:
    print(f"{r.evaluator}: {r.score:.2f} ({r.label})")
```

Evaluators run **after** the strategy completes, in configured
order. The `RunResult` carries every result on `eval_scores`.

### How do I pick deterministic vs LLM-judge?

| Use deterministic when… | Use LLM-judge when… |
|---|---|
| Ground truth is structured (expected items, schema) | Ground truth is fuzzy ("did it answer the question?") |
| You need every-run scoring (no LLM cost) | You only need scoring on a sample |
| Score must be reproducible across runs | Subjective judgement is acceptable |
| Output is a fixed format | Output is open-ended prose |

Mix and match — deterministic graders are free (`cost_estimate_usd =
0.0`) and run on every call; LLM judges are budget-gated and skip
when remaining budget falls below their declared cost.

### How does budget gating work?

Before each evaluator's `evaluate(...)`, the run loop checks
`budget.remaining_usd() >= evaluator.cost_estimate_usd`. If not,
the grader is skipped and `agentforge.evaluators` logs a WARN.
Skipped graders don't appear in `result.eval_scores`.

Tighten budgets to cap judge cost:

```python
# Total $5 cap; if the strategy spent $4.95, only graders declaring
# <= $0.05 will run.
agent = Agent(model="...", evaluators=[judge_grader], budget_usd=5.0)
```

Each grader declares its own estimate. The G-Eval engine defaults
to `0.01`; override per-instance via the `cost_estimate_usd=`
kwarg if your judge is cheaper / more expensive.

### How do I use a cheap judge for an expensive agent?

```python
from agentforge_bedrock import BedrockClient
from agentforge_eval_geval import Correctness

# Cheap judge (Haiku) scores Sonnet-powered agent output.
judge = BedrockClient(model_id="us.anthropic.claude-haiku-4-5")

agent = Agent(
    model="bedrock:us.anthropic.claude-sonnet-4-5-20250929",
    evaluators=[Correctness(judge=judge)],
)
```

Separate judge models reduce cost **and** reduce the "judge agrees
with itself" bias when the same model answers and scores. The
named-provider config from feat-003 makes this a config edit when
feat-012 ships.

### How do I write a custom rubric?

Use `GEval` directly with a dict rubric:

```python
from agentforge_eval_geval import GEval

grader = GEval(
    judge=judge,
    name="pr-description-quality",
    rubric={
        "criteria": "Score whether the PR description accurately describes the diff.",
        "scoring": "1.0 = accurate and complete; 0.0 = inaccurate or empty",
        "inputs": ["diff"],   # injects context['diff'] into the prompt
        "examples": [
            {"output": "...", "score": 0.9, "reasoning": "..."},
        ],
    },
    cost_estimate_usd=0.005,
)
```

Or load a YAML rubric file shipped in your agent's repo:

```python
grader = GEval.from_rubric_file("./rubrics/pr-quality.yaml", judge=judge)
```

The judge must return a JSON object with `score` (float in [0, 1])
and `reasoning` (string). The engine parses defensively — markdown
fences, chatter before/after the JSON, score-out-of-range are all
tolerated.

### How do I score against a baseline?

Lock a baseline file (JSONL, one entry per task with `task` +
`expected` keys), then point `RegressionVsBaseline` at it:

```python
# baselines/v0.4.jsonl
{"task": "Summarise PR #42", "expected": "PR #42 adds X."}
{"task": "List failing tests", "expected": ["test_a", "test_b"]}
```

```python
from agentforge.eval import RegressionVsBaseline

agent = Agent(
    model="...",
    evaluators=[
        RegressionVsBaseline(baseline_path="./baselines/v0.4.jsonl"),
    ],
)
```

Default mode is `exact` (string equality). For structured outputs:

```python
RegressionVsBaseline(baseline_path="...", mode="structural")
```

→ score = matching keys / total keys; `raw` carries
`missing_keys`, `extra_keys`, `mismatched_keys`. Tasks without a
baseline entry get `score=NaN`, label `"no_baseline"` — the grader
doesn't claim regression in that case.

### How do I check consistency across re-runs?

```python
from agentforge.eval import Consistency

async def rerun(task: str) -> str:
    async with Agent(model="...") as sub_agent:
        sub_result = await sub_agent.run(task)
        return sub_result.output

agent = Agent(
    model="...",
    evaluators=[Consistency(runner=rerun, n_samples=3)],
)
```

The runner is the seam — pass a function that returns the new
output for a task. Score is `agreements / n_samples`. The re-runs'
LLM cost bills against the runner's own `Agent` (or whatever the
runner calls); use the same `budget_usd` to keep the run within a
unified cap.

### How do I read what each evaluator decided?

```python
result = await agent.run("…")
by_name = {r.evaluator: r for r in result.eval_scores}
print(by_name["correctness"].score, by_name["correctness"].label)
print(by_name["faithfulness"].reasoning)
print(by_name["coverage"].raw["missing"])
```

`EvalResult.raw` is grader-specific — `Coverage` reports
`matched/missing/extracted`, `PatchFinding`'s renderer reports
hunk info, `GEval` reports `judge_cost_usd`, `judge_tokens_in`,
`judge_tokens_out`, and `raw_text`.

### How do I debug "an evaluator never ran"?

Most common cause: budget exhausted before the evaluator's turn.
Look for `WARN agentforge.evaluators: skipping evaluator ...` in
logs. Fix: lower the judge's `cost_estimate_usd` if it's
over-declared, or raise `budget_usd` enough to cover both the run
and the evaluator pass.

Second cause: the grader raised an exception inside `evaluate`. The
loop catches LLM-call failures inside `GEval` and turns them into
`fail` `EvalResult`s, but a bug in a custom grader's `evaluate`
will propagate — wrap it in a `try` if you want soft failure.

### When should I NOT add an evaluator?

- **Real-time gating.** Evaluators score *after* the run; they
  cannot refuse a tool call or redact PII before output. Use
  feat-018 safety guardrails for inline defenses.
- **Per-step scoring** (mid-loop). Evaluators are post-run only.
  For per-step assertions, write a custom `ReasoningStrategy`
  subclass that asserts in its body.
- **Catastrophic-failure detection.** A `fail` `EvalResult` is
  informational — it doesn't raise. If you need the run to fail
  hard on a score below threshold, check `result.eval_scores`
  yourself after `await agent.run(...)` and raise.
