# agentforge-langfuse

Langfuse trace dashboard hook for the AgentForge framework.

Implements the `StepHook` + `FinishHook` contracts and
registers as `agentforge.hooks:langfuse`.

## Installation

```bash
pip install agentforge-langfuse[langfuse]
```

The `[langfuse]` extra pulls in the `langfuse>=2.0` SDK.
Without it, the production factory raises `ModuleError` with
pip remediation.

## Usage

```python
from agentforge import Agent
from agentforge_langfuse import LangfuseHook

hook = LangfuseHook.from_config(
    public_key="pk-lf-...",
    secret_key="sk-lf-...",
    host="https://cloud.langfuse.com",
    trace_name_prefix="agentforge.pr-reviewer",
)

agent = Agent(
    model="bedrock:...",
    on_step=hook,
    on_finish=hook,
)
```

## Trace shape

- One **trace** per run, opened on the first step (keyed by
  `run_id`).
- One **span** per step (`name = "step:<kind>"`).
- A **nested span** per `tool_call` (`name = "tool:<name>"`).
- Two **scores** on finish: `cost_usd` and `duration_ms`.
- The trace is `flush()`-ed at finish so it lands in the
  dashboard without waiting for the SDK's batch interval.

## License

Apache-2.0.
