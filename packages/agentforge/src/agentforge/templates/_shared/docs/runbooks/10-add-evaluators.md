# 10 — Add evaluators

> **Goal:** score each agent run on quality so regressions are
> caught before they ship.
> **Time:** ~20 minutes.
> **Prereqs:** runbook 06.

## TL;DR

```yaml
# agentforge.yaml
modules:
  evaluators:
    - name: faithfulness        # LLM-judge
    - name: coverage            # deterministic
      config:
        required_facts: ["population", "year"]
    - name: regression-vs-baseline
      config:
        baseline_path: ./tests/baselines/answers.jsonl
```

```bash
agentforge eval --fixtures ./tests/golden.jsonl --threshold 0.8
```

## Step by step

1. **Mix deterministic + LLM-judge.** Deterministic graders
   (coverage, format-compliance, regression-vs-baseline,
   consistency) are cheap; ship them everywhere. Use LLM-judge
   graders (faithfulness, groundedness, hallucination,
   relevance, helpfulness, correctness) when no rule captures
   the property — they cost LLM calls per evaluation.
2. **Declare under `modules.evaluators`.** Each entry has a
   `name` (resolver key) and optional `config`. The framework
   instantiates and runs them post-run, attaching scores to
   `RunResult.eval_scores`.
3. **Wire into CI.** `agentforge eval --fixtures golden.jsonl
   --threshold 0.8 --output-format junit > eval.xml` exits 5
   when the mean score is below the threshold.
4. **Threshold per evaluator** (when one matters more than the
   others) goes in the evaluator's own `config` block.
5. **Custom evaluators** subclass `Evaluator` and register with
   `@register("evaluators", "my-name")`. Run
   `run_evaluator_conformance(my_eval)` to verify the contract.

## Variations

- **Cost gating** — each LLM-judge declares
  `cost_estimate_usd`. `BudgetPolicy` skips them when the run's
  remaining budget would be exceeded.
- **GEval rubrics** — `agentforge-eval-geval` lets you define
  arbitrary judge rubrics in YAML.
- **Snapshot diff** — for outputs that should stay byte-stable,
  pair an evaluator with `agentforge_testing.assert_snapshot`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No module registered for evaluators:faithfulness` | LLM-judge pkg missing | `agentforge add module eval-geval` |
| Evaluators didn't run | budget exhausted before eval pass | bump `agent.budget.usd` or drop expensive judges |
| Threshold pass but quality regressed | mean masked outliers | switch CI to per-fixture threshold or run with `--threshold-per-evaluator` |
| Judge gives same score every time | judge prompt too vague | tighten the rubric; add 2-3 worked examples |

## Related

- Runbook 06 — Test your agent
- Runbook 12 — Add observability (eval scores feed dashboards)
- Feature spec: `docs/features/feat-006-evaluators-and-benchmarks.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
