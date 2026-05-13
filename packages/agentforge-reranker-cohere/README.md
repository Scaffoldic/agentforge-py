# agentforge-reranker-cohere

Cohere managed-API reranker for the AgentForge framework.

Implements the `Reranker` ABC from `agentforge-core`.
Registers as `agentforge.rerankers:cohere`.

## Installation

```bash
pip install agentforge-reranker-cohere[cohere]
```

## Usage

```python
from agentforge_reranker_cohere import CohereReranker

reranker = CohereReranker.from_config(
    api_key="...",
    model="rerank-english-v3.0",
)
```

Or via `agentforge.yaml`:

```yaml
retrieval:
  reranker:
    name: cohere
    config:
      api_key: ${COHERE_API_KEY}
      model: rerank-english-v3.0
```

The reranker forwards `(query, candidate_text)` pairs to
Cohere's Rerank API, normalises the returned scores to
`[0, 1]` (Cohere already does this — the clamp is
defensive), sorts descending, and truncates to `top_k`.

## License

Apache-2.0.
