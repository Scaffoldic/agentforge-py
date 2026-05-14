# agentforge-ollama

Ollama local LLM + embedding provider for
[AgentForge](https://github.com/Scaffoldic/agentforge-py).

Talks to a local [Ollama](https://ollama.com) server (default
`http://localhost:11434`). Use it for fully-local agents, dev
loops without an API budget, or to run open-weight models
(`llama3`, `qwen3`, `mistral`, `mxbai-embed-large`) under the
same `LLMClient` / `EmbeddingClient` contracts as the cloud
providers.

## Install

```bash
pip install "agentforge-ollama[ollama]"
```

You also need the Ollama daemon running locally:

```bash
ollama serve
ollama pull llama3.2:3b
```

## Use

```python
from agentforge import Agent

agent = Agent(model="ollama:llama3.2:3b")
```

## Capabilities

`OllamaClient.capabilities()` declares `{"tools", "streaming"}`
when the model advertises tool support (the server reports this
via `/api/show`). Caching / extended thinking / vision are not
surfaced — Ollama doesn't expose them through a uniform API.

Cost is always zero (local inference).

## License

Apache-2.0. See [LICENSE](./LICENSE).
