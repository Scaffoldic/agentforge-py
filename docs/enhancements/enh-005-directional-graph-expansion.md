# enh-005: directional graph expansion for GraphRAG

> Improves a *shipped* feature (feat-023, GraphRAG hybrid retrieval). Not a
> defect — graph expansion works as designed — this adds a `direction` knob so
> expansion can follow **asymmetric** edges the right way (callers vs callees,
> who-cites vs what-it-cites). It stays entirely within the locked `GraphStore`
> contract, which already exposes `get_edges(direction=...)`, so there is **no
> ABC change**.

---

## Metadata

| Field | Value |
|---|---|
| **ID** | enh-005 |
| **Title** | `direction` on `GraphExpansion` (in / out / any) |
| **Status** | accepted (targeted at the 0.4 train) |
| **Owner** | kjoshi |
| **Created** | 2026-06-17 |
| **Target version** | 0.4 |
| **Languages** | `python` (TS deferred) |
| **Improves** | feat-023 (GraphRAG hybrid retrieval) |
| **Module package(s)** | `agentforge-core` (`GraphExpansion` value + config schema), `agentforge` (`Retriever` expansion) |

---

## 1. Why this enhancement

feat-023 expands a retrieved seed by walking the graph up to `max_hops`,
optionally filtered to `edge_types` (so expansion is already **typed**). But it
walks those edges **without a direction** — `GraphStore.traverse()` has no
direction parameter, so expansion treats every edge as undirected.

For **symmetric** relationships (`RELATED_TO`, `SIMILAR`) that's fine. For
**asymmetric** ones it loses precision, because the two directions answer
different questions:

| Relationship | Out-edges (`X → ?`) | In-edges (`? → X`) |
|---|---|---|
| `CITES` | what X cites | who cites X |
| `CALLS` | what X calls (callees) | who calls X (callers) |
| `IMPORTS` | X's dependencies | X's dependents |
| `REPORTS_TO` | X's manager chain | X's reports |

Today an agent asking "who cites this paper?" gets X's *own* citations mixed in
— noise that dilutes the candidate set and the reranker's budget. The fix is a
single **`direction`** control on the expansion policy.

## 2. Why it must ship as framework

- **Expansion is a retrieval-time policy decision** — the same argument feat-023
  makes for owning graph expansion at all. *Direction* is part of that policy;
  pushing it into agent code re-forks the merge/decay/dedup logic the framework
  deliberately centralised.
- **It needs cross-driver consistency.** "In/out/any" must mean the same thing
  over Neo4j, SurrealDB, and the embedded driver. The framework already defines
  that vocabulary on `GraphStore.get_edges(direction=...)`; this surfaces it at
  the retrieval layer.
- **It stays inside the locked contract.** `get_edges(direction=...)` is already
  part of the v0.1 `GraphStore` ABC — so the capability is reachable with **no
  ABC change and no major-version bump**. This is the clean, contract-respecting
  way to add it.
- **Without framework ownership:** every agent post-filters expansion results by
  direction itself — re-implementing (often incorrectly) what the store can do
  natively, and losing it the moment they switch graph backends.

## 3. How derived agents benefit

One new optional key; no code:

```yaml
retrieval:
  graph_expansion:
    store: { driver: kuzu, config: { path: .ckg } }
    edge_types: [CITES]
    direction: in            # ← NEW: "who cites this", not "what this cites"
    max_hops: 2
```

- Precise expansion for asymmetric graphs (citation networks, call graphs,
  supply chains, org charts).
- **Fully backward compatible:** `direction` defaults to `"any"`, which is
  exactly today's behaviour — existing configs and `Retriever(...)` calls are
  unchanged, bit for bit.

## 4. Feature specifications

### 4.1 User-facing experience
- `retrieval.graph_expansion` gains an optional `direction: in | out | any`
  (default `any`).
- `GraphExpansion(direction=...)` constructs the same policy programmatically.

### 4.2 Public API / contract

```python
# agentforge_core/values/retrieval.py
class GraphExpansion(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, arbitrary_types_allowed=True)
    store: GraphStore
    max_hops: int = 2
    edge_types: tuple[str, ...] | None = None
    direction: Literal["out", "in", "any"] = "any"   # NEW
    text_property: str = "text"
    decay: float = 0.5

# agentforge_core/config/schema.py
class GraphExpansionConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    store: ModuleEntry
    max_hops: int = Field(default=2, ge=1)
    edge_types: tuple[str, ...] | None = None
    direction: Literal["out", "in", "any"] = "any"   # NEW
    text_property: str = "text"
    decay: float = Field(default=0.5, gt=0.0, le=1.0)
```

**No change to the `GraphStore` ABC.** Direction is consumed via the existing
`get_edges(node_id, *, edge_type, direction)` method.

### 4.3 Internal mechanics
The `Retriever`'s `_expand_via_graph` (feat-023) gains a directional path:

- **`direction == "any"`** → unchanged: call `store.traverse(start_id,
  edge_types, max_depth, limit)` exactly as today. Existing behaviour preserved.
- **`direction in {"out", "in"}`** → directional BFS in the retriever using the
  locked primitive: for each hop up to `max_hops`, expand the frontier via
  `store.get_edges(node_id, edge_type=t, direction=direction)` for each `t` in
  `edge_types` (or all types when `edge_types is None`), collecting the
  neighbour on the appropriate end (`dst` for `out`, `src` for `in`).
- **Neighbour synthesis is identical to feat-023** — per neighbour at `depth`:
  `score = seed.score * decay**depth`, metadata carries
  `agentforge.expanded_from` + `agentforge.hop`; dedup by id with direct hits
  winning. Only *which* neighbours are gathered changes; the merge/decay/dedup
  pipeline is reused verbatim.

This keeps `direction="any"` on the optimized native `traverse()` path while
giving precise directional control where it matters — without touching the ABC.

### 4.4 Module packaging
- `GraphExpansion` value + `GraphExpansionConfig` change in `agentforge-core`.
- `Retriever` expansion change in `agentforge`.
- **No new package** (same footprint as feat-023).

### 4.5 Configuration
```yaml
retrieval:
  graph_expansion:
    store: { driver: neo4j, config: { uri: bolt://localhost:7687 } }
    edge_types: [CALLS]
    direction: in           # callers; omit or set "any" for current behaviour
    max_hops: 3
    decay: 0.5
```

## 5. Plug-and-play & upgrade story
- `direction` defaults to `"any"` → **zero behavioural change** for existing
  agents; existing YAML and `Retriever(...)` calls keep identical results.
- Opt in by adding the one key. Works across every `graph_stores` driver,
  because it rides on the contract's `get_edges(direction=...)`.

## 6. Cross-language parity
TypeScript port deferred (mirrors feat-023). The direction semantics map onto
the same `get_edges` direction vocabulary; the TS port mirrors 1:1 when
scheduled.

## 7. Test strategy
- **Value validation** — `direction` accepts only `in|out|any`; default `any`.
- **Expansion correctness** — over a fixture graph with asymmetric edges:
  `direction="in"` returns predecessors (callers), `"out"` returns successors
  (callees), `"any"` returns the prior (undirected) set.
- **Combination** — `direction` + `edge_types` together (e.g. in-edges of type
  `CALLS` only).
- **Backward compatibility** — `direction="any"` (and omitted) produce results
  byte-identical to the pre-change `traverse()` path.
- **Decay / dedup unchanged** — same scores and dedup outcomes as feat-023 for
  the neighbours gathered.
- Uses the in-memory reference graph store; fully offline.

## 8. Risks & open questions
- **`traverse()` vs `get_edges` performance.** For `direction="any"` we keep the
  (possibly DB-optimized) `traverse()` path; directional expansion does its BFS
  via `get_edges`, which may issue more calls on dense graphs. Bounded by
  `max_hops` + the existing candidate cap; documented.
- **Per-edge-type direction.** Some questions want different directions per edge
  type in one pass (e.g. `CALLS` in **and** `IMPORTS` out). v1 keeps a single
  `direction` for the whole expansion; per-type direction is a future
  extension (an agent can run two expansions meanwhile).

## 9. Out of scope
- A `direction` parameter on `GraphStore.traverse()` — that would change the
  **locked** ABC (major bump); deliberately avoided by using `get_edges`.
- Per-edge-type direction maps.
- Native single-query directional expansion inside Neo4j/SurrealDB.
- TypeScript port.

## 10. References
- feat-023 (GraphRAG hybrid retrieval — the feature this improves).
- feat-027 (embedded `KuzuGraphStore` — ships on the same 0.4 train; its
  `get_edges(direction=...)` is the embedded path this rides).
- `GraphStore` contract — `get_edges(direction=...)` (the locked primitive used).

## 11. Implementation status (Python)
**Status: accepted, not yet implemented.** Suggested chunking:
1. Spec + catalogue/roadmap pointer.
2. `direction` on `GraphExpansion` + `GraphExpansionConfig`; `_expand_via_graph`
   directional branch via `get_edges`; unit tests incl. backward-compat.
3. Status flip + CHANGELOG + runbook note on feat-023.

## 12. Runbook

### How do I expand only along callers / dependents / who-cites?
Set `direction: in` in the `graph_expansion` block (with the relevant
`edge_types`). For callees / dependencies / what-it-cites, use `direction: out`.
Omit it (or `any`) to keep the original undirected expansion.

```yaml
retrieval:
  graph_expansion:
    store: { driver: kuzu, config: { path: .ckg } }
    edge_types: [CALLS]
    direction: in        # callers of the seed, up to max_hops
    max_hops: 2
```

### Will this change my existing agent's results?
No. `direction` defaults to `any`, which is the pre-enhancement behaviour. You
opt in per retrieval config.
