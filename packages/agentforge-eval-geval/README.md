# agentforge-eval-geval

LLM-judge evaluators for AgentForge (feat-006).

This package ships the **G-Eval** engine — an LLM-as-judge grader
that scores agent outputs against a rubric YAML — plus six named
graders that wrap G-Eval with reference rubrics:

| Grader | Scores |
|---|---|
| `Correctness` | Output matches the ground-truth answer (rubric-tunable for binary / Likert / ordinal) |
| `Faithfulness` | Output is *supported by* the retrieved evidence (no claims beyond what was retrieved) |
| `Groundedness` | Output *stays inside* the provided sources (no off-source content) |
| `Hallucination` | Output contains content not derivable from inputs (faithfulness + groundedness combined into a single risk score) |
| `Relevance` | Output addresses the user's question vs going off-topic |
| `Helpfulness` | Output is useful — actionable, complete, well-structured |

Each grader takes a judge `LLMClient` at construction. The judge is
typically a cheaper model than the agent's primary model (e.g. Haiku
judging Sonnet output) — cuts cost and reduces "judge agrees with
itself" bias.

## Quick start

```python
from agentforge import Agent
from agentforge_bedrock import BedrockClient
from agentforge_eval_geval import Correctness, Faithfulness

judge = BedrockClient(model_id="us.anthropic.claude-haiku-4-5")

agent = Agent(
    model="bedrock:us.anthropic.claude-sonnet-4-5-20250929",
    evaluators=[
        Correctness(judge=judge, ground_truth_field="expected"),
        Faithfulness(judge=judge, sources_field="retrieved_docs"),
    ],
)
result = await agent.run("Summarise PR #42")
print(result.eval_scores)
```

Cost-bounded: each judge call bills against the run's `BudgetPolicy`
(feat-007). When the remaining budget falls below the grader's
`cost_estimate_usd`, the agent skips the grader and logs a WARN.

## Custom rubrics with G-Eval

```python
from agentforge_eval_geval import GEval

grader = GEval(
    judge=judge,
    name="code-review-quality",
    rubric={
        "criteria": "Score the PR description's accuracy and completeness.",
        "scoring": "0.0 = incorrect/incomplete; 1.0 = accurate and complete",
        "examples": [
            {"output": "...", "score": 0.9, "reasoning": "..."},
        ],
    },
)
```

Or load from a YAML file:

```python
grader = GEval.from_rubric_file("./rubrics/code-review.yaml", judge=judge)
```
