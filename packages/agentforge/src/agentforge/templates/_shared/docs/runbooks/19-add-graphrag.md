# 19 — Add GraphRAG (graph-augmented retrieval)

> **Goal:** enrich top-k retrieval with N-hop neighbours from a
> graph store, so an answer about "Alice" also pulls in
> "Alice's manager" and "Alice's recent project".
> **Time:** ~15 minutes.
> **Prereqs:** runbooks 08 + 18. A populated `GraphStore`.

## TL;DR

```yaml
# agentforge.yaml
retrieval:
  mode: hybrid
  embedder:
    driver: openai
    config: {model: text-embedding-3-small}
  vector_store:
    driver: postgres
    config: {dsn: $POSTGRES_DSN, table: docs}
  graph_expansion:             # the new bit
    graph_store: people_graph  # named graph store from modules.graph_stores
    max_hops: 1
    relations: [reports_to, works_on]
    score_decay: 0.5            # neighbour score = parent_score * decay
  top_k: 12
modules:
  graph_stores:
    people_graph:
      driver: neo4j
      config: {uri: $NEO4J_URI, user: neo4j, password: $NEO4J_PASSWORD}
```

## Step by step

1. **Decide which entities you'll expand.** Pick a small set
   of relation types (`reports_to`, `cited_by`, ...). Expanding
   on everything destroys precision; one or two hops is enough.
2. **Populate the graph.** Either pre-build it (ETL job) or use
   the agent itself: the `agentforge_core.contracts.graph`
   surface has `add_triple` / `query_neighbors`.
3. **Add a `graph_expansion:` block** under `retrieval:`. The
   `Retriever` runs vector / hybrid first, then expands each
   top-k hit's entity via the named `GraphStore`, applies the
   `score_decay` per hop, and re-ranks the merged list.
4. **Set `max_hops` conservatively.** Start with `1`; `2` is
   for "explain why" queries where context chains matter.
5. **Tune `score_decay`.** `0.5` halves a neighbour's score
   versus its parent at hop 1; lower decay = neighbours
   compete; higher decay = neighbours augment without
   overwhelming.

## Variations

- **Composes with anything else.** GraphRAG is post-retrieve,
  so it works with `mode: vector` or `hybrid`, with or without
  a reranker (rerank happens after expansion).
- **Sparse expansion** — only expand the top-1 hit
  (`expand_top_n: 1`) when you want extra context only for the
  best match.
- **Different graph per tenant** — name several graph stores
  in `modules.graph_stores` and switch via dotted-path env
  overrides (`AGENTFORGE_RETRIEVAL__GRAPH_EXPANSION__GRAPH_STORE=tenant_graph`).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No neighbours returned | entity IDs in vector store don't match graph node IDs | confirm the `id` field matches across stores |
| Latency 3-4x | hop 2+ on a wide graph | drop `max_hops` to 1, narrow `relations` |
| Neighbour scores too high | `score_decay` ≥ 0.8 | lower toward 0.5 |
| Wrong neighbours | over-broad `relations` list | pin to the specific relations the query cares about |

## Related

- Runbook 08 — Add memory + retrieval
- Runbook 18 — Add hybrid search
- Feature spec: `docs/features/feat-023-graphrag-hybrid.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
