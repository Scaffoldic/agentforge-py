# 17 — Add a reranker

> **Goal:** improve retrieval precision by re-scoring the top-k
> candidates a vector store returned, then keeping the best.
> **Time:** ~10 minutes.
> **Prereqs:** runbook 08 (retrieval already wired).

## TL;DR

```yaml
# agentforge.yaml
retrieval:
  embedder:
    driver: voyage
    config: {model: voyage-3-large}
  vector_store:
    driver: postgres
    config: {dsn: $POSTGRES_DSN, table: docs}
  reranker:
    name: cohere               # or: sentence_transformers / voyage / mixedbread
    config:
      api_key: $COHERE_API_KEY
      model: rerank-english-v3.0
      top_k: 4                  # keep the top 4 after re-scoring
```

## Step by step

1. **Pick a reranker driver.** Built-in choices:
   - `sentence_transformers` — local cross-encoder; no API key, slower.
   - `cohere` — managed; fast; needs `COHERE_API_KEY`.
   - `voyage` — managed; high quality; needs `VOYAGE_API_KEY`.
   - `mixedbread` — managed; needs `MIXEDBREAD_API_KEY`.
2. **Install the matching package.**
   `agentforge add module reranker-cohere` (or `-voyage`,
   `-mixedbread`, `-sentence-transformers`).
3. **Drop the `reranker:` block** into `retrieval:`. The
   `Retriever` looks up the driver via the `agentforge.rerankers`
   entry-point category and slots it after the vector / hybrid
   search stage.
4. **Set `top_k`.** The reranker runs over the vector store's
   `top_k_pre` candidates and returns `top_k`. Common settings:
   `top_k_pre=20, top_k=4` for cost-aware, `top_k_pre=50,
   top_k=8` for quality-aware.
5. **Test it.** `await retriever.retrieve("query")` returns
   `VectorMatch` rows already in reranked order — the
   `score` field reflects the reranker's score, not the
   original vector similarity.

## Variations

- **Two-stage** — keep an embedding-based fast path with a
  reranker only on cold queries. Set
  `retrieval.reranker.always: false`.
- **Custom reranker** — implement the `Reranker` ABC in
  `agentforge_core.contracts.reranker` and register it via the
  `agentforge.rerankers` entry-point in your module's
  `pyproject.toml`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No reranker registered for X` | package not installed | `agentforge add module reranker-X` |
| Latency 2-3x higher | local cross-encoder on CPU | switch to managed (Cohere / Voyage) |
| Top result is wrong | reranker model mismatch with corpus language | pick the matching `rerank-multilingual-v3.0` or similar |
| Cost spike | reranker called per request, hot path | cache by query hash or move reranker to async batch path |

## Related

- Runbook 08 — Add memory + retrieval
- Runbook 18 — Add hybrid search
- Feature spec: `docs/features/feat-021-reranker.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
