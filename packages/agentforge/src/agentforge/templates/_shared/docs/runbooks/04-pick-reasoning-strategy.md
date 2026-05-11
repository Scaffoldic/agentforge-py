# 04 — Pick a reasoning strategy

> **Goal:** choose the right `ReasoningStrategy` for your task.
> **Time:** ~5 minutes.
> **Prereqs:** runbook 01 done.

## TL;DR

```yaml
# agentforge.yaml
agent:
  strategy: react              # default — most agents stay here
  # strategy: plan-execute     # multi-step plans with verification
  # strategy: tree-of-thoughts # search over candidate paths
  # strategy: multi-agent      # supervisor + worker fan-out
```

## Step by step

1. **Default to ReAct.** It's the simplest stable loop: think →
   act → observe. Most agent failures come from prompts or
   tools, not the loop itself. Switching strategies on Day 1 is
   premature.
2. **Move to Plan-Execute** when the task naturally decomposes
   into a plan + execution: code reviewers, multi-file edits,
   research with structured outputs.
3. **Move to Tree-of-Thoughts** when you have a verifier and
   need to explore multiple candidate paths. Expensive — only
   when the task warrants it.
4. **Move to Multi-Agent** when distinct sub-agents have
   meaningfully different system prompts / tool sets (security
   reviewer + style reviewer + correctness reviewer).
5. **Measure before switching** — runbook 10 covers evaluators.
   Don't change strategy without a baseline.

## Variations

- **Custom strategy** — subclass `ReasoningStrategy` and
  register via `@register("strategies", "my-name")`. Run
  `run_strategy_conformance` from `agentforge.testing` against
  it.
- **Iteration cap** — `agent.max_iterations` (default 25) is
  enforced by every shipped strategy; ToT respects it
  per-branch.
- **Budget reservation** — strategies coordinate with
  `BudgetPolicy` automatically; you don't need to thread cost
  manually.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Agent loops indefinitely | tool observations too vague to make progress | improve tool docstrings + observation strings |
| `iteration_cap` finish_reason | max_iterations too low | bump it or switch to Plan-Execute |
| Plan-Execute "plan" step is junk | system prompt didn't give planning hints | seed examples in the prompt; runbook 05 |
| ToT cost spike | verifier too lenient, expanding too many branches | tighten verifier prompt; cap `max_branches` |

## Related

- Runbook 05 — Write prompts
- Runbook 10 — Add evaluators (baseline before switching)
- Feature spec: `docs/features/feat-002-reasoning-strategies.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
