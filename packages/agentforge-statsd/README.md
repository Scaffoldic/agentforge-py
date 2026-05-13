# agentforge-statsd

StatsD metrics emitter for the AgentForge framework.

Implements the `StepHook` + `FinishHook` contracts on the
existing `agentforge.hooks` entry-point so installing the
package makes `name: statsd` available in
`modules.observability` config blocks.

## Installation

```bash
pip install agentforge-statsd[statsd]
```

The `[statsd]` extra pulls in the `statsd>=4.0` Python client.
Without the extra, the package is importable but the
production factory raises `ModuleError` with pip remediation.

## Usage

```python
from agentforge import Agent
from agentforge_statsd import StatsdHook

hook = StatsdHook.from_config(
    host="statsd.internal",
    port=8125,
    prefix="agentforge.pr-reviewer",
)

agent = Agent(
    model="bedrock:...",
    on_step=hook,
    on_finish=hook,
)
```

## Metrics emitted

| Metric | Type | When |
|---|---|---|
| `<prefix>.step.<kind>` | counter +1 | every step |
| `<prefix>.step.duration_ms` | timing | every step with `duration_ms > 0` |
| `<prefix>.tool.<name>` | counter +1 | every step with `tool_call` |
| `<prefix>.run.finish.<reason>` | counter +1 | on run finish |
| `<prefix>.run.duration_ms` | timing | on run finish |
| `<prefix>.run.cost_usd` | gauge | on run finish |
| `<prefix>.run.tokens_in` | gauge | on run finish |
| `<prefix>.run.tokens_out` | gauge | on run finish |

## License

Apache-2.0.
