# agentforge-phoenix

Arize Phoenix dashboard hook for the AgentForge framework.

Implements the `StepHook` + `FinishHook` contracts and
registers as `agentforge.hooks:phoenix`.

## Installation

```bash
pip install agentforge-phoenix[phoenix]
```

## Usage

```python
from agentforge import Agent
from agentforge_phoenix import PhoenixHook

hook = PhoenixHook.from_config(
    endpoint="http://localhost:6006",
    project_name="my-agent",
)

agent = Agent(
    model="bedrock:...",
    on_step=hook,
    on_finish=hook,
)
```

## Logged events

- **`log_run`** — once per `RunResult` at finish, carrying
  `run_id`, `finish_reason`, `cost_usd`, `tokens_in`,
  `tokens_out`, `duration_ms`.
- **`log_step`** — once per `Step`, carrying `iteration`,
  `kind`, `duration_ms`, `cost_usd`.
- **`log_tool_call`** — once per `step.tool_call`, carrying
  the tool name + redacted argument shape.

Phoenix's OTel-compatible exporter can also receive
`agentforge-otel` spans without this package; install this
hook when you want explicit Phoenix project-namespaced
logging (e.g. when you want every run in a single project
view).

## License

Apache-2.0.
