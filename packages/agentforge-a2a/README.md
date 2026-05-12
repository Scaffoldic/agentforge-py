# agentforge-a2a

A2A (Agent-to-Agent) protocol support for AgentForge: cross-framework
agent invocation over HTTP, with bearer / mTLS auth, run_id chain,
and budget propagation.

See [`docs/features/feat-014-a2a-protocol.md`](https://github.com/Scaffoldic/agentforge-py/blob/main/docs/features/feat-014-a2a-protocol.md)
for the design and runbook.

## Install

```bash
pip install agentforge-a2a
# or, from a scaffolded project:
agentforge add module a2a
```

## Call another agent

```python
from agentforge_a2a import A2APeer, agent_call

peer = A2APeer.from_config({
    "name": "fact-checker",
    "url": "https://internal.fact-checker.example/a2a",
    "auth": {"type": "bearer", "token": "${FACT_CHECKER_TOKEN}"},
})

result = await agent_call(
    "fact-checker:verify",
    {"claim": "The capital of Australia is Sydney."},
    timeout_s=30,
    peers={"fact-checker": peer},
)
print(result.output)
```

## Expose this agent

```python
from agentforge import Agent, EnvBearerAuth
from agentforge_a2a import A2AServer

server = A2AServer(
    agent=Agent(model="anthropic:claude-sonnet-4-6", strategy="react"),
    auth=EnvBearerAuth("A2A_TOKENS"),
    endpoints=["review-pr"],
    host="0.0.0.0",
    port=8080,
)
await server.serve()
```
