# Roadmap

What's planned but not yet shipped. Each entry is a
"feature-in-flight" with a rough scope; the full design lands in a PR
when work begins. Items are listed by feature number, not priority —
order may shift based on user demand.

## In flight

*No numbered features in flight — every feat-NNN entry has shipped.
Pick the next one from the backlog when starting.*

---

## Backlog (no design yet)

These are tracked here so they don't get lost. Designs land when
they get prioritised:

- **feat-004 — Anthropic SDK direct provider.** First-party Anthropic
  client (not via Bedrock). Mirrors the locked `LLMClient` surface
  feat-003 exercises.
- **feat-005 — OpenAI / Azure provider.** Same shape as feat-004.
- **feat-006 — `agentforge-eval-geval`.** Cheap-judge model + eval
  framework. Closes the `scorer="judge"` placeholder from feat-002's
  `TreeOfThoughts`.
- **feat-010 — Entry-point auto-loader.** `pip install agentforge-X`
  alone enables `Agent(model="X:...")` without an explicit import.
- **GraphRAG-style hybrid retrieval** (post-feat-009). Combines vector
  retrieval with graph expansion — pull the top-k vector matches,
  then traverse outgoing edges to enrich context.
- **Hybrid search** (BM25 + vector fusion) inside the locked
  `VectorStore` capability vocabulary.
- **Reranker contract** — `Reranker` ABC for cross-encoder reranking
  on top of `VectorStore.search`.
- **Schema migrations** for persistent stores (Postgres, SQLite). Lands
  alongside the first breaking schema delta.
