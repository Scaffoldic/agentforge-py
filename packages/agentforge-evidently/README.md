# agentforge-evidently

Evidently AI agent metrics + drift hook for the AgentForge
framework.

Implements the `StepHook` + `FinishHook` contracts and
registers as `agentforge.hooks:evidently`.

## Installation

```bash
pip install agentforge-evidently[evidently]
```

## Usage

```python
from agentforge import Agent
from agentforge_evidently import EvidentlyHook

hook = EvidentlyHook.from_config(
    project="my-agent",
    report_dir="./evidently-reports",
)

agent = Agent(
    model="bedrock:...",
    on_step=hook,
    on_finish=hook,
)
```

## What gets reported

Per-step records (one row per `Step`):

| Column | Source |
|---|---|
| `run_id` | bound `RunContext.run_id` |
| `iteration` | `step.iteration` |
| `kind` | `step.kind` |
| `cost_usd` | `step.cost_usd` |
| `tokens_in` / `tokens_out` | `step.tokens_in` / `step.tokens_out` |
| `duration_ms` | `step.duration_ms` |
| `has_tool_call` | `step.tool_call is not None` |

At finish, the hook appends a run-level row and writes an
Evidently `Report` JSON to
`<report_dir>/<run_id>.json`. The report carries the buffered
rows + `RunResult.finish_reason` + `RunResult.cost_usd` so an
offline analysis pipeline can compute drift / quality metrics
across runs.

## License

Apache-2.0.
