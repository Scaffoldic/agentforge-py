# agentforge-memory-surrealdb

SurrealDB-backed `MemoryStore`, `VectorStore`, and `GraphStore` for the
AgentForge framework.

## What this is

SurrealDB is uniquely multi-modal: a single store supports documents,
graphs, and vectors. This package implements all three locked
contracts against one SurrealDB connection:

- **`SurrealMemoryStore`** — claim audit log
- **`SurrealVectorStore`** — semantic search (HNSW index)
- **`SurrealGraphStore`** — knowledge graph traversal via
  `RELATE` / `->edge->` SurrealQL syntax

All three pass the locked
`agentforge_core.testing.run_*_conformance` suites.

## Usage

```python
from agentforge_memory_surrealdb import (
    SurrealGraphStore,
    SurrealMemoryStore,
    SurrealVectorStore,
)

async with SurrealGraphStore.from_url(
    "ws://localhost:8000/rpc",
    namespace="agentforge",
    database="dev",
    auth=("root", "root"),
) as store:
    await store.add_node(GraphNode(id="paper:1", labels=("Doc",)))
    ...
```

## Local development

```bash
docker compose -f docker-compose.dev.yml up -d
RUN_LIVE_SURREAL=1 SURREAL_URL=ws://localhost:8000/rpc \
  uv run pytest packages/agentforge-memory-surrealdb/tests/integration -v
```

## Capabilities

- **Graph**: `{"transactions", "surrealql", "vector", "live_query"}`
- **Vector**: `{"native_ann"}` (when `init_schema()` provisions the
  HNSW index)
- **Memory**: `{"transactions"}`
