# agentforge-reranker-sentence-transformers

SentenceTransformers cross-encoder reranker for the AgentForge
framework (feat-021 default concrete impl).

Registers as `agentforge.rerankers:sentence-transformers` and
implements the `Reranker` ABC from `agentforge-core`.

## Installation

```bash
pip install agentforge-reranker-sentence-transformers[sentence-transformers]
```

The `[sentence-transformers]` extra pulls in
`sentence-transformers>=3.0` (~500MB for base + one model).
Without it, the production factory raises `ModuleError` with
pip remediation.

## Usage

```python
from agentforge import Retriever
from agentforge_reranker_sentence_transformers import (
    SentenceTransformersReranker,
)

reranker = SentenceTransformersReranker.from_config(
    model="cross-encoder/ms-marco-MiniLM-L-6-v2",
)
retriever = Retriever(
    store=vector_store,
    embedder=embedding_client,
    reranker=reranker,
    over_fetch_factor=3,
)
results = await retriever.retrieve("how do I deploy?", top_k=5)
```

## Score normalisation

The cross-encoder returns raw logits (typically `-10..+10`).
The reranker applies a sigmoid (`1 / (1 + exp(-x))`) so
returned scores are normalised to `(0, 1)` — fitting the
`VectorMatch.score` contract from `agentforge-core`.

## License

Apache-2.0.
