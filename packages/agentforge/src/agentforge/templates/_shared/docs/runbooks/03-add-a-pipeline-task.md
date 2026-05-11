# 03 — Add a pipeline task

> **Goal:** insert a deterministic, non-LLM step into the agent's
> workflow (e.g. parse a file, call a metric API, normalise
> input).
> **Time:** ~15 minutes.
> **Prereqs:** runbook 02 (you understand tools).

## TL;DR

```python
from agentforge import Pipeline, Task

class FetchPRMetadata(Task):
    async def run(self, *, pr_url: str) -> dict:
        return await my_github_client.get_pr(pr_url)

pipeline = Pipeline([FetchPRMetadata, AgentStep, RenderReport])
```

## Step by step

1. **Identify deterministic boundaries** — anything that has a
   stable function from inputs to outputs (file parsing, API
   normalisation, score thresholding) is a Task, not an LLM call.
2. **Author the Task** — subclass `Task`; declare typed inputs
   and outputs; `async def run(...)` is the body.
3. **Compose** with `Pipeline([T1, T2, T3])` — tasks run in
   order, each receiving the previous one's output.
4. **Mix LLM steps** — use the framework's `AgentStep` wrapper
   to drop an agent run into a pipeline; the surrounding tasks
   handle deterministic pre/post processing.
5. **Capture failures** — Tasks raise `TaskError` for
   recoverable cases; the framework surfaces it as a step in
   the agent's trace.

## Variations

- **Parallel tasks** — `Pipeline.parallel([T1, T2])` runs them
  concurrently and joins their outputs into a dict.
- **Conditional branching** — wrap with `Pipeline.branch(
  condition_fn, true_pipe, false_pipe)`.
- **Retry** — set `retries=N` on the Task class; the framework
  re-runs with exponential backoff.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Task output not visible to LLM | task didn't make output visible to the agent step | thread output through `AgentStep`'s task context |
| Pipeline fails fast on first error | default behaviour | wrap with `Pipeline.tolerant(...)` for best-effort runs |
| Memory blows up on large pipelines | task results held in RAM | persist intermediate outputs to memory store (runbook 08) |

## Related

- Runbook 02 — Add a tool (different shape: tools are LLM-
  invoked, tasks are deterministic)
- Runbook 08 — Add memory
- Feature spec: `docs/features/feat-015-pipelines-and-deterministic-tasks.md`

> **Note:** Pipelines + Tasks are feat-015 territory. If your
> framework version pre-dates that feature, this runbook is
> aspirational — fall back to wrapping deterministic steps as
> tools.

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
