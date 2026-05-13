# agentforge-reranker-voyage

Voyage AI managed-API reranker for the AgentForge framework.

Registers as `agentforge.rerankers:voyage`. Implements the
`Reranker` ABC from `agentforge-core`.

## Installation

```bash
pip install agentforge-reranker-voyage[voyage]
```

## Usage

```yaml
retrieval:
  reranker:
    name: voyage
    config:
      api_key: ${VOYAGE_API_KEY}
      model: rerank-2
```

```python
from agentforge_reranker_voyage import VoyageReranker

reranker = VoyageReranker.from_config(
    api_key="...",
    model="rerank-2",
)
```

## License

Apache-2.0.
