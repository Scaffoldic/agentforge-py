# agentforge-memory-kuzu

Embedded, file-backed `GraphStore` for [AgentForge](https://github.com/Scaffoldic/agentforge-py),
backed by [Kùzu](https://kuzudb.com/) — a persistent property graph in a
single directory, in-process, no server (feat-027).

It is the graph analogue of the SQLite `MemoryStore`: zero-ops local
development, CI, single-host deployments, and embedded products. The driver
implements the locked `GraphStore` contract and passes
`run_graph_conformance`, so it is swap-compatible with the Neo4j and
SurrealDB drivers.

```python
from agentforge_memory_kuzu import KuzuGraphStore
from agentforge_core.values.graph import GraphNode, GraphEdge

async with await KuzuGraphStore.from_path(".ckg") as store:
    await store.add_node(GraphNode(id="a", labels=("Func",)))
    await store.add_node(GraphNode(id="b", labels=("Func",)))
    await store.add_edge(GraphEdge(src="b", dst="a", edge_type="CALLS"))
    callers = await store.get_edges("a", edge_type="CALLS", direction="in")
```

Via YAML, anywhere a `graph_stores` driver is accepted:

```yaml
store:
  driver: kuzu
  config:
    path: .ckg          # directory; created if absent
```
