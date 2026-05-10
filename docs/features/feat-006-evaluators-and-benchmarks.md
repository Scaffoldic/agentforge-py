# feat-006: Evaluators & benchmarks

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-006 |
| **Title** | Evaluators — `Evaluator` ABC, built-in graders, LLM-judge |
| **Status** | proposed |
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
