# agentforge-memory-sqlite

SQLite-backed `MemoryStore` and `VectorStore` for [AgentForge](https://github.com/Scaffoldic/agentforge-py).

Zero external services required — the database lives in a single file
(or `:memory:` for tests). Suitable for development, single-host
deployments, and small-to-medium RAG corpora (~10k vectors).

## Install

```bash
uv add agentforge-memory-sqlite
```

## Usage

```python
from agentforge_memory_sqlite import SqliteMemoryStore, SqliteVectorStore

# Claim audit log
async with SqliteMemoryStore.from_path("agent.db") as memory:
    await memory.put(claim)

# Semantic search
async with SqliteVectorStore.from_path("agent.db", dimensions=1024) as store:
    await store.upsert(items)
    matches = await store.search(query_vector, limit=5)
```

Both classes pass `agentforge_core.testing.run_memory_conformance` /
`run_vector_conformance` so they're drop-in replacements for the
in-memory defaults.

## Performance

`SqliteVectorStore` does brute-force cosine search in Python: O(N) per
query. Fine for ~10k vectors; sluggish past that. v0.2 will add an
opt-in `sqlite-vec` extension path declared via the `"native_ann"`
capability flag.
