# feat-027: Embedded GraphStore (file-backed, zero-ops graph driver)

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-027 |
| **Title** | `KuzuGraphStore` — embedded, file-backed `GraphStore` driver |
| **Status** | accepted (targeted at the 0.4 train) |
| **Owner** | kjoshi |
| **Created** | 2026-06-17 |
| **Target version** | 0.4 |
| **Languages** | `python` (TS deferred) |
| **Module package(s)** | new `agentforge-memory-kuzu` (registers `KuzuGraphStore` under the `graph_stores` entry-point category) |
| **Depends on** | feat-005 (`GraphStore` ABC + conformance), ADR-0007 (locked surface) |
| **Blocks** | none |

---

## 1. Why this feature

Every shipped `GraphStore` driver — `Neo4jGraphStore`, `SurrealGraphStore` —
requires a **separate database server** to be provisioned, networked, and
authenticated before an agent can store a single node. There is no graph store
that lives at a **local file path**, in-process, the way SQLite serves the
relational `MemoryStore` and the way `InMemoryGraphStore` serves tests (but
without persistence).

That gap is felt the moment an agent wants a real graph for **local
development, CI, a single-host deployment, or an embedded product**: the only
options today are "stand up Neo4j" (operationally heavy) or "hand-roll a
store" (re-inventing the contract). The natural configuration for a local graph
is simply a path —

```yaml
store: { driver: kuzu, config: { path: .ckg } }
```

— and nothing currently satisfies it. An **embedded, file-backed
`GraphStore`** closes the gap: a persistent property graph in a single
directory, no server, no network, started in milliseconds.

## 2. Why it must ship as framework

- **`GraphStore` is a framework-locked ABC (ADR-0007).** Adding a driver is the
  standard contribution shape; every agent benefits from one more backend
  behind the same surface.
- **The `graph_stores` entry-point category already exists** (Neo4j, SurrealDB,
  and the in-memory reference register there). An embedded, persistent driver
  is the missing **zero-ops** member of that set — the graph analogue of the
  SQLite `MemoryStore`.
- **Cross-driver conformance guarantees behaviour.** The driver must pass
  `run_graph_conformance`, so it is swap-compatible with Neo4j/SurrealDB —
  upsert idempotency, edge-readback, pattern match, depth-bounded traversal,
  and cascade-delete semantics are identical.
- **Offline-first is a framework value.** An embedded store makes the *entire*
  graph + GraphRAG path testable with no server and no credentials, matching
  the framework's offline-replay ethos.
- **Without framework ownership:** every agent that wants a local graph either
  pulls in a heavyweight server or writes a bespoke store that drifts from the
  contract and can't be swapped.

## 3. How derived agents benefit

A scaffolded agent gets a persistent graph with **no infrastructure**, by config
alone:

```yaml
# agentforge.yaml
retrieval:
  graph_expansion:
    store: { driver: kuzu, config: { path: .ckg } }   # was: a Neo4j server
    max_hops: 2
```

- **Zero setup** — `path: .ckg` and the store exists; nothing to install or run.
- **Swap-by-config, no code** — because it obeys the same `GraphStore` contract,
  an agent can develop on `kuzu` locally and switch to `neo4j` for a shared
  deployment by changing one line.
- **GraphRAG plugs in unchanged** — feat-023 consumes any `graph_stores` driver,
  so an embedded store works with graph expansion immediately.
- **Fully offline tests** — agents can build and traverse a real persisted graph
  in CI with no service dependency.

## 4. Feature specifications

### 4.1 User-facing experience
- `KuzuGraphStore.from_path(path)` — ergonomic construction at a directory
  (mirrors `SqliteMemoryStore.from_path`). The store opens (or creates) an
  embedded database under `path`.
- `from_config(*, path)` — the standard module-construction convention, so the
  driver builds from a `config:` block.
- Implements the full locked `GraphStore` surface (`add_node`, `add_edge`,
  `get_edges`, `match`, `traverse`, `delete_node`, `delete_edge`, `close`).
- Declares optional `capabilities()` it can honour (candidates: `"transactions"`,
  `"fulltext"`; `"vector"` only if a `KuzuVectorStore` is added later — out of
  scope here).

### 4.2 Public API / contract

```python
class KuzuGraphStore(GraphStore):
    def __init__(self, *, connection: KuzuConnection) -> None: ...

    @classmethod
    async def from_path(cls, path: str | Path) -> "KuzuGraphStore":
        """Open or create an embedded graph database under `path`."""

    @classmethod
    async def from_config(cls, *, path: str | Path) -> "KuzuGraphStore": ...

    # all GraphStore abstract methods, conformance-verified
```

- **Node/edge mapping.** `GraphNode(id, labels, properties)` →
  a node record keyed on `id`; `GraphEdge(src, dst, edge_type, properties)` →
  a typed relationship. `add_node`/`add_edge` are **idempotent upserts** (re-add
  by `id` / `(src, dst, edge_type)` replaces `properties`), per the ABC.
- **Edge integrity.** `add_edge` raises `ValueError` if `src`/`dst` are unknown
  nodes — the contract's well-formedness rule.
- **`get_edges(direction=...)`** maps to the embedded engine's directional edge
  lookup (the primitive feat-023's directional expansion — enh-005 — relies on).

### 4.3 Internal mechanics
- **Storage.** A single embedded database directory at `path`; opened in-process,
  no server. Schema (node table + a generic typed-relationship table) is created
  lazily on first write.
- **Upserts.** Implemented via the engine's merge/replace semantics keyed on the
  stable ids, matching the ABC's idempotency invariant.
- **`traverse`.** Variable-length / recursive query bounded by `max_depth` and
  `limit`; returns `Path` objects with `len(edges) == len(nodes) - 1` in chain
  order (conformance-checked).
- **`match`.** Pattern evaluated by the engine's query language; same `Path`
  return shape as the Cypher/SurrealQL drivers.
- **`delete_node(cascade)`.** `cascade=True` removes incident edges; `cascade=False`
  raises if edges remain (no orphaned edges) — the contract rule.
- **Concurrency.** Embedded single-writer; documented (see Risks). `close()`
  releases the file handle.

### 4.4 Module packaging
- New sister package **`agentforge-memory-kuzu`** (mirrors the
  `agentforge-memory-neo4j` / `-surrealdb` packages that host graph drivers).
- `pyproject.toml` registers
  `[project.entry-points."agentforge.graph_stores"]` → `kuzu = "agentforge_memory_kuzu:KuzuGraphStore"`.
- Versioned in lockstep on the coordinated release train (ADR-0015).

### 4.5 Configuration
```yaml
# anywhere a graph_stores driver is accepted (e.g. retrieval.graph_expansion.store)
store:
  driver: kuzu
  config:
    path: .ckg          # directory; created if absent
```

## 5. Plug-and-play & upgrade story
- Purely additive — a new entry-point member. Existing configs and drivers are
  untouched.
- Any feature that consumes a `graph_stores` driver (notably GraphRAG, feat-023)
  works with `kuzu` immediately, no changes.
- Switching to/from another graph driver is a one-line config change; data
  migration between backends is a separate concern (out of scope).

## 6. Cross-language parity
TypeScript port deferred (same posture as the other graph/retrieval features).
The contract surface and conformance suite are language-agnostic; the TS port
mirrors this 1:1 when scheduled.

## 7. Test strategy
- **Conformance** — `run_graph_conformance` against a real embedded database in
  a temp dir. This is the headline: a persistent driver fully exercised
  **offline, no server, no credentials**.
- **Unit** — `from_path`/`from_config` construction; upsert idempotency;
  edge-integrity `ValueError`; `get_edges` direction; cascade-delete; `close`.
- **Live gating** — **not required** (embedded), unlike Neo4j/SurrealDB which
  gate on `RUN_LIVE_*`. This is a deliberate advantage.
- **Cross-platform** — note the native dependency (see Risks); CI matrix must
  cover the supported wheels.

## 8. Risks & open questions
- **Native dependency.** The embedded engine ships a compiled component; the
  package must pin to platforms with available wheels and document the support
  matrix. Mitigation: keep it an opt-in sister package (installing
  `agentforge` core is unaffected).
- **Concurrency model.** Embedded engines are typically single-writer. Document
  the constraint; an agent doing concurrent writes (e.g. a file-watcher
  re-indexer) must serialise. Aligns with how SQLite is treated.
- **File locking under watch loops.** Long-lived readers + a re-indexing writer
  need a clear locking story; surfaced in the runbook.

## 9. Out of scope
- `KuzuVectorStore` (the engine can index embeddings) — a natural follow-up so
  one embedded file serves graph **and** vector, but a separate spec.
- Cross-backend data migration / export-import.
- TypeScript port.

## 10. References
- `GraphStore` contract + ADR-0007 (locked surface).
- `agentforge_core.testing.run_graph_conformance` (the cross-driver suite this
  driver must pass).
- feat-005 (GraphStore + drivers), feat-023 (GraphRAG — the primary consumer).
- enh-005 (directional graph expansion — relies on this driver's
  `get_edges(direction=...)` for the embedded path).

## 11. Implementation status (Python)
**Status: accepted, not yet implemented.** Suggested chunking when built:
1. Spec + catalogue row + roadmap pointer.
2. `KuzuGraphStore` class + entry-point registration + `from_path`/`from_config`
   + conformance pass (offline).
3. Capability gating (`fulltext`/`transactions` as honoured) + runbook.
4. Status flip + catalogue + roadmap + CHANGELOG.

## 12. Runbook

### How do I use an embedded graph store?
```python
from agentforge_memory_kuzu import KuzuGraphStore

async with await KuzuGraphStore.from_path(".ckg") as store:
    await store.add_node(GraphNode(id="a", labels=("Func",)))
    await store.add_node(GraphNode(id="b", labels=("Func",)))
    await store.add_edge(GraphEdge(src="b", dst="a", edge_type="CALLS"))
    callers = await store.get_edges("a", edge_type="CALLS", direction="in")
```
Via YAML: set `driver: kuzu, config: { path: .ckg }` anywhere a `graph_stores`
driver is accepted.

### When should I NOT use it?
- Multi-writer / shared-service deployments → use `neo4j`.
- You already run Neo4j/SurrealDB for other stores → reuse it for one DB.

### How does it compare to the in-memory store?
`InMemoryGraphStore` is ephemeral (test fixture). This driver **persists** to a
path and survives process restarts — the embedded, production-capable local
option.
