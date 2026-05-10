# agentforge-memory-neo4j

Neo4j-backed `MemoryStore` and `GraphStore` for the AgentForge
framework.

## What this is

- **`Neo4jMemoryStore`** — `MemoryStore` (claim audit log) over Neo4j.
  Claims map to `(:Claim {…})` nodes; queries become parameterised
  Cypher.
- **`Neo4jGraphStore`** — `GraphStore` (knowledge graph traversal)
  over Neo4j. Nodes and edges map directly to property graph nodes
  and relationships. `match()` and `traverse()` compile to Cypher.

Both pass the locked `agentforge_core.testing.run_*_conformance`
suites — drop-in alternatives to `agentforge-memory-sqlite` when you
need real graph semantics, multi-writer concurrency, or production
operability (clustering, fine-grained auth, query planner).

## Usage

```python
from agentforge_memory_neo4j import Neo4jGraphStore

async with Neo4jGraphStore.from_url(
    "bolt://localhost:7687",
    auth=("neo4j", "password"),
    database="neo4j",
) as store:
    await store.add_node(GraphNode(id="paper:1", labels=("Doc",)))
    ...
```

## Local development

```bash
docker compose -f docker-compose.dev.yml up -d
RUN_LIVE_NEO4J=1 NEO4J_URL=bolt://localhost:7687 \
  NEO4J_USER=neo4j NEO4J_PASSWORD=test \
  uv run pytest packages/agentforge-memory-neo4j/tests/integration -v
```

## Capabilities

`{"transactions", "cypher", "fulltext"}` — Neo4j 5.x ships native
fulltext indexes; transactions are first-class (every write goes
through `session.execute_write`).

Vector search is *not* declared: Neo4j 5.x has vector indexes but
adopting them is tracked separately. Pair Neo4j with
`agentforge-memory-postgres` (pgvector) or `agentforge-memory-sqlite`
for embeddings.
