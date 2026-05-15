# 18 — Add hybrid search (BM25 + vector)

> **Goal:** combine keyword (BM25) and semantic (vector) recall
> so queries that hit a specific term don't get out-voted by
> "close-but-wrong" embeddings.
> **Time:** ~10 minutes.
> **Prereqs:** runbook 08 (retrieval wired).

## TL;DR

```yaml
# agentforge.yaml
retrieval:
  mode: hybrid               # one of: vector | hybrid | bm25
  embedder:
    driver: openai
    config: {model: text-embedding-3-small}
  vector_store:
    driver: postgres         # native FTS via tsvector + ts_rank_cd
    config:
      dsn: $POSTGRES_DSN
      table: docs
      hybrid:
        alpha: 0.6           # weight on semantic (0=BM25-only, 1=vector-only)
  top_k: 8
```

## Step by step

1. **Pick a vector store with native hybrid.** Every shipped
   driver supports `lexical_search` as of v0.2:
   - `postgres` — Postgres `tsvector` + `ts_rank_cd`
   - `sqlite` — SQLite FTS5 + `bm25`
   - `neo4j` — Neo4j fulltext index + `score`
   - `surrealdb` — SurrealDB `DEFINE ANALYZER` + `SEARCH ANALYZER ... BM25`
   - `in_memory` — pure-Python BM25 (good for tests)
2. **Set `retrieval.mode: hybrid`.** The `Retriever` then runs
   the vector pass and the lexical pass in parallel and fuses
   the result lists via Reciprocal Rank Fusion (RRF).
3. **Tune `alpha`.** Higher `alpha` weights vector recall;
   lower weights BM25. Start at 0.6 and bisect against your
   golden-set evaluator.
4. **(Optional) Add a reranker** on top — see runbook 17.
   Hybrid → rerank is the canonical RAG quality stack.
5. **Index your corpus.** Postgres / SQLite need a one-time
   index creation (the v0.2 migration framework handles this
   — see runbook 20).

## Variations

- **bm25 only** — for keyword-dominant corpora (logs, code).
  `mode: bm25` skips the embedder entirely.
- **Tenant-scoped hybrid** — pass `tenant_id` through the
  retriever; both passes filter on it before fusion.
- **Async indexing** — large corpora benefit from a background
  job that bulk-inserts then refreshes the lexical index.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Hybrid returns same results as vector | `alpha=1.0` or BM25 index missing | tune `alpha` and confirm the lexical migration applied |
| Latency 2x vector-only | sequential passes | upgrade `agentforge-memory-*` to v0.2 — the passes run in parallel |
| `lexical_search not supported` | older driver version | upgrade the driver package |
| Top BM25 hits dominate | low `alpha` + short queries | raise `alpha` toward 0.7 |

## Related

- Runbook 08 — Add memory + retrieval
- Runbook 17 — Add a reranker
- Runbook 20 — Apply schema migrations
- Feature spec: `docs/features/feat-022-hybrid-search.md`
- Feature spec: `docs/features/feat-025-neo4j-vector-store.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
