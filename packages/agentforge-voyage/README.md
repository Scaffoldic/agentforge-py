# agentforge-voyage

Voyage AI embedding provider for
[AgentForge](https://github.com/Scaffoldic/agentforge-py).

Implements `EmbeddingClient` over Voyage's `embeddings.create()`
API. Embedding-only — Voyage doesn't ship a chat model. Use it
when you want Voyage's RAG-optimised embeddings paired with any
chat provider (Anthropic, OpenAI, Bedrock).

## Install

```bash
pip install "agentforge-voyage[voyage]"
```

## Use

```python
from agentforge_voyage import VoyageEmbeddingClient

emb = VoyageEmbeddingClient.from_config(
    model="voyage-3-large",
    api_key="pa-...",  # or omit and use VOYAGE_API_KEY
)
resp = await emb.embed(["hello", "world"])
print(resp.vectors[0])
```

## Capabilities

`{"multimodal"}` for `voyage-multimodal-3`; empty set otherwise.

## License

Apache-2.0. See [LICENSE](./LICENSE).
