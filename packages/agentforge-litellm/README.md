# agentforge-litellm

LiteLLM router-based LLM provider for
[AgentForge](https://github.com/Scaffoldic/agentforge-py).

Wraps [LiteLLM](https://github.com/BerriAI/litellm)'s unified
interface so a single AgentForge agent can route to 100+
underlying providers (OpenAI, Anthropic, Bedrock, Vertex, Azure,
Mistral, Groq, Fireworks, Together, ...) by changing the model
string — no per-provider sister package needed.

When to use this vs. a native sister package:

- **Prefer native** (`agentforge-anthropic`, `agentforge-openai`,
  ...) for production paths where you want first-class
  capability surface (caching, thinking, streaming with full
  type-checked stream events).
- **Use LiteLLM** as a unified gateway, for tail providers
  AgentForge doesn't ship native packages for yet, or to
  experiment with new models behind a single config.

## Install

```bash
pip install "agentforge-litellm[litellm]"
```

## Use

```python
from agentforge import Agent

# Model string is "litellm:<litellm-model-string>". The second
# half is whatever LiteLLM accepts.
agent = Agent(model="litellm:gpt-4o-mini")
agent = Agent(model="litellm:anthropic/claude-sonnet-4-7")
agent = Agent(model="litellm:bedrock/anthropic.claude-sonnet-4-7")
```

## Capabilities

`{"tools"}` only. LiteLLM normalises tools across underlying
providers but doesn't expose a uniform caching / thinking /
vision / streaming surface — those vary per backend. If you
need those, use the matching native sister package.

## License

Apache-2.0. See [LICENSE](./LICENSE).
