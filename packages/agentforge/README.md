# agentforge

The default runtime for the AgentForge framework — `Agent`, `ReActLoop`,
default tools, `SimpleFinding`, in-memory store, basic safety defaults,
`BudgetPolicy`. Most users install this package and add module extras
as needed.

## Three-line agent (once feat-001 lands)

```python
from agentforge import Agent

agent = Agent(model="anthropic:claude-sonnet-4.7")
result = await agent.run("Say hello in three words.")
```

## Install

```bash
pip install agentforge                              # core runtime
pip install "agentforge[anthropic]"                 # + Anthropic provider
pip install "agentforge[anthropic,memory-postgres]" # + persistence
```

## Status

v0.0 — pre-alpha. Repo bootstrapped; feat-001 (Core contracts &
`Agent` orchestrator) is the next milestone.

## License

Apache 2.0.
