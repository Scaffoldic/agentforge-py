# agentforge-openai

OpenAI native LLM + embedding provider for
[AgentForge](https://github.com/Scaffoldic/agentforge-py).

Implements both `LLMClient` and `EmbeddingClient` against
OpenAI's `chat.completions.create()` (gpt-4o / o-series) and
`embeddings.create()` (text-embedding-3-small / -large).

## Install

```bash
pip install "agentforge-openai[openai]"
```

The bare `pip install agentforge-openai` install keeps the
package importable for tests; the production runner needs the
`openai` SDK, which the `[openai]` extra pulls in.

## Use

```python
from agentforge import Agent
from agentforge_openai import OpenAIClient, OpenAIEmbeddingClient

# Chat
agent = Agent(model="openai:gpt-4o-mini")

# Embeddings (direct construction)
emb = OpenAIEmbeddingClient.from_config(
    model="text-embedding-3-small",
    api_key="sk-...",
)
```

## Capabilities

`OpenAIClient.capabilities()` declares: `tools`, `json_mode`,
`streaming`, `vision` (for `gpt-4o*` variants). Caching and
extended thinking are not surfaced (OpenAI handles caching
transparently; o-series internal reasoning is not exposed as a
budget-able knob through the public API today).

## License

Apache-2.0. See [LICENSE](./LICENSE).
