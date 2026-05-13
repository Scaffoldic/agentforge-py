# agentforge-reranker-mixedbread

Mixedbread AI managed-API reranker for the AgentForge
framework.

Registers as `agentforge.rerankers:mixedbread`. Implements
the `Reranker` ABC from `agentforge-core`.

## Installation

```bash
pip install agentforge-reranker-mixedbread[mixedbread]
```

## Usage

```yaml
retrieval:
  reranker:
    name: mixedbread
    config:
      api_key: ${MIXEDBREAD_API_KEY}
      model: mixedbread-ai/mxbai-rerank-large-v1
```

```python
from agentforge_reranker_mixedbread import MixedbreadReranker

reranker = MixedbreadReranker.from_config(
    api_key="...",
    model="mixedbread-ai/mxbai-rerank-large-v1",
)
```

## License

Apache-2.0.
