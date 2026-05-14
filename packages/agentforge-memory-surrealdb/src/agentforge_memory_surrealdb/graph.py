"""`SurrealGraphStore` — `GraphStore` over SurrealDB via SurrealQL.

SurrealDB models graphs natively: every record is potentially a node,
and `RELATE src->edge_table->dst` creates a graph edge that's also a
record (with its own id and properties). Pattern matching uses
`->edge->`, `<-edge<-`, `<->edge<->` syntax.

Mapping strategy:
  - Nodes live in the `af_node` table with a generated id derived from
    `node.id` (SurrealDB ids are namespaced as `table:id`). The
    framework `id` becomes the SurrealDB record id; `labels` and
    `properties` are stored as record fields.
  - Edges use the `af_edge` graph table. SurrealQL `RELATE`
    distinguishes them automatically. `edge_type` is a property on
    the edge record (we use a single edge table rather than per-type
    tables so the surface stays portable across schema vocabularies).

Capabilities: `{"transactions", "surrealql", "vector", "live_query"}`.
"""

from __future__ import annotations

from collections import deque
from types import TracebackType
from typing import Any, Literal

from agentforge_core.contracts.graph_store import GraphStore
from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    Path,
)
from surrealdb import AsyncSurreal

from agentforge_memory_surrealdb._migrator import SurrealMigrator
from agentforge_memory_surrealdb._runner import SurrealRunner, _SurrealClientRunner

# Table names are framework constants — never derived from user input.
# All SurrealQL queries are constructed from these constants only,
# never from caller-supplied strings, so the S608 SQL-injection
# warnings on the f-strings below are false positives. We keep the

_NODE_TABLE = "af_node"
_EDGE_TABLE = "af_edge"

_INIT_SCHEMA_QUERY = (
    f"DEFINE TABLE IF NOT EXISTS {_NODE_TABLE} SCHEMALESS;"
    f"DEFINE TABLE IF NOT EXISTS {_EDGE_TABLE} TYPE RELATION SCHEMALESS;"
    f"DEFINE INDEX IF NOT EXISTS {_NODE_TABLE}_id_idx "
    f"ON {_NODE_TABLE} FIELDS af_id UNIQUE;"
)

_UPSERT_NODE_QUERY = (
    f"UPSERT type::thing('{_NODE_TABLE}', $id) "
    "CONTENT { af_id: $id, labels: $labels, properties: $properties }"
)
_SELECT_NODE_BY_ID = f"SELECT * FROM {_NODE_TABLE} WHERE af_id = $id LIMIT 1"  # noqa: S608  # nosec B608
_SELECT_NODES_BY_IDS = f"SELECT af_id FROM {_NODE_TABLE} WHERE af_id IN $ids"  # noqa: S608  # nosec B608
_SELECT_ALL_NODES = f"SELECT * FROM {_NODE_TABLE}"  # noqa: S608  # nosec B608
_DELETE_NODE = f"DELETE FROM {_NODE_TABLE} WHERE af_id = $id"  # noqa: S608  # nosec B608

_DELETE_EDGE_BY_TRIPLE = (
    f"DELETE FROM {_EDGE_TABLE} WHERE "  # noqa: S608  # nosec B608
    "in.af_id = $src AND out.af_id = $dst AND edge_type = $edge_type"
)
_RELATE_EDGE = (
    f"LET $s = (SELECT * FROM {_NODE_TABLE} WHERE af_id = $src)[0]; "  # noqa: S608  # nosec B608
    f"LET $d = (SELECT * FROM {_NODE_TABLE} WHERE af_id = $dst)[0]; "
    f"RELATE $s->{_EDGE_TABLE}->$d "
    "CONTENT { edge_type: $edge_type, properties: $properties }"
)
_SELECT_EDGE_BY_TRIPLE = (
    f"SELECT id FROM {_EDGE_TABLE} WHERE "  # noqa: S608  # nosec B608
    "in.af_id = $src AND out.af_id = $dst AND edge_type = $edge_type"
)
_DELETE_EDGES_INCIDENT = (
    f"DELETE FROM {_EDGE_TABLE} WHERE "  # noqa: S608  # nosec B608
    "in.af_id = $id OR out.af_id = $id"
)


def _select_edges(where: str) -> str:
    """Compose an `af_edge` SELECT — `where` is a constant predicate
    chosen from a closed set in `get_edges`, never user input."""
    return (
        f"SELECT in.af_id AS src, out.af_id AS dst, edge_type, properties "  # noqa: S608  # nosec B608
        f"FROM {_EDGE_TABLE} WHERE {where}"
    )


class SurrealGraphStore(GraphStore):
    """`GraphStore` over SurrealDB."""

    def __init__(self, *, runner: SurrealRunner) -> None:
        self._r = runner

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        namespace: str = "agentforge",
        database: str = "default",
        auth: tuple[str, str] | None = None,
    ) -> SurrealGraphStore:
        client = AsyncSurreal(url)
        if auth is not None:
            await client.signin({"username": auth[0], "password": auth[1]})
        await client.use(namespace, database)
        return cls(runner=_SurrealClientRunner(client))

    async def __aenter__(self) -> SurrealGraphStore:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    def migrator(self) -> SurrealMigrator:
        """Return a `SurrealMigrator` configured against the package's
        bundled migrations directory (feat-024)."""
        return SurrealMigrator(self._r)

    async def init_schema(self) -> None:
        """Apply every bundled migration (idempotent). Opt-in.

        Delegates to the feat-024 migration framework — schema
        provisioning is now versioned + checksum-tracked.
        """
        await self.migrator().apply_pending()

    async def close(self) -> None:
        await self._r.close()

    # ------------------------------------------------------------------
    # GraphStore contract
    # ------------------------------------------------------------------

    async def add_node(self, node: GraphNode) -> None:
        await self._r.query(
            _UPSERT_NODE_QUERY,
            {
                "id": node.id,
                "labels": list(node.labels),
                "properties": dict(node.properties),
            },
        )

    async def add_edge(self, edge: GraphEdge) -> None:
        # Verify both endpoints exist.
        rows = await self._r.query(_SELECT_NODES_BY_IDS, {"ids": [edge.src, edge.dst]})
        present = _flatten_ids(rows)
        missing = [nid for nid in (edge.src, edge.dst) if nid not in present]
        if missing:
            msg = f"add_edge: node(s) {missing!r} do not exist"
            raise ValueError(msg)

        # Idempotent on (src, dst, edge_type): delete then RELATE.
        await self._r.query(
            _DELETE_EDGE_BY_TRIPLE,
            {"src": edge.src, "dst": edge.dst, "edge_type": edge.edge_type},
        )
        await self._r.query(
            _RELATE_EDGE,
            {
                "src": edge.src,
                "dst": edge.dst,
                "edge_type": edge.edge_type,
                "properties": dict(edge.properties),
            },
        )

    async def get_node(self, node_id: str) -> GraphNode | None:
        rows = await self._r.query(_SELECT_NODE_BY_ID, {"id": node_id})
        records = _flatten(rows)
        if not records:
            return None
        return _record_to_node(records[0])

    async def get_edges(
        self,
        node_id: str,
        *,
        edge_type: str | None = None,
        direction: Literal["out", "in", "any"] = "out",
    ) -> list[GraphEdge]:
        if direction == "out":
            where = "in.af_id = $id"
        elif direction == "in":
            where = "out.af_id = $id"
        else:
            where = "(in.af_id = $id OR out.af_id = $id)"
        if edge_type is not None:
            where += " AND edge_type = $edge_type"
        params = (
            {"id": node_id, "edge_type": edge_type} if edge_type is not None else {"id": node_id}
        )
        rows = await self._r.query(_select_edges(where), params)
        return [_record_to_edge(r) for r in _flatten(rows)]

    async def match(self, pattern: GraphPattern, *, limit: int = 50) -> list[Path]:
        if limit < 1:
            msg = f"limit must be >= 1, got {limit}"
            raise ValueError(msg)

        # SurrealQL multi-segment pattern composition is non-trivial;
        # for v0.1 we issue an `af_edge`-table SELECT and filter
        # client-side. This is correct for any segment count and lets
        # us reuse the same path-reconstruction logic across drivers.
        # The conformance suite tests one segment, which this handles
        # natively; multi-segment is uncommon in agent code paths.
        return await _walk_match_clientside(self, pattern, limit)

    async def traverse(
        self,
        start_id: str,
        *,
        edge_types: tuple[str, ...] | None = None,
        max_depth: int = 3,
        limit: int = 50,
    ) -> list[Path]:
        if max_depth < 1:
            msg = f"max_depth must be >= 1, got {max_depth}"
            raise ValueError(msg)
        if limit < 1:
            msg = f"limit must be >= 1, got {limit}"
            raise ValueError(msg)
        start = await self.get_node(start_id)
        if start is None:
            return []

        # BFS expansion using `get_edges` + `get_node`. SurrealDB has
        # native graph syntax (`->af_edge*1..N->`), but spelling it
        # out portably across SurrealDB versions is fiddly; the
        # client-side BFS is correct and trivially testable.
        return await _bfs_traverse(self, start, edge_types, max_depth, limit)

    async def delete_node(self, node_id: str, *, cascade: bool = False) -> bool:
        existing = await self.get_node(node_id)
        if existing is None:
            return False
        edges = await self.get_edges(node_id, direction="any")
        if edges and not cascade:
            msg = (
                f"delete_node: {node_id!r} has {len(edges)} incident edge(s); "
                "pass cascade=True to remove them"
            )
            raise ValueError(msg)
        if cascade:
            await self._r.query(_DELETE_EDGES_INCIDENT, {"id": node_id})
        await self._r.query(_DELETE_NODE, {"id": node_id})
        return True

    async def delete_edge(self, src: str, dst: str, *, edge_type: str) -> bool:
        # Probe first so we can return an honest True/False.
        rows = await self._r.query(
            _SELECT_EDGE_BY_TRIPLE,
            {"src": src, "dst": dst, "edge_type": edge_type},
        )
        if not _flatten(rows):
            return False
        await self._r.query(
            _DELETE_EDGE_BY_TRIPLE,
            {"src": src, "dst": dst, "edge_type": edge_type},
        )
        return True

    def capabilities(self) -> set[str]:
        return {"transactions", "surrealql", "vector", "live_query"}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _flatten(rows: list[Any]) -> list[dict[str, Any]]:
    """SurrealDB query() returns either a list of row dicts or a list
    of lists (one per statement). Normalise to a flat list of dicts."""
    if not rows:
        return []
    flat: list[dict[str, Any]] = []
    for item in rows:
        if isinstance(item, dict):
            flat.append(item)
        elif isinstance(item, list):
            flat.extend(x for x in item if isinstance(x, dict))
    return flat


def _flatten_ids(rows: list[Any]) -> set[str]:
    return {str(r["af_id"]) for r in _flatten(rows) if r.get("af_id") is not None}


def _record_to_node(record: dict[str, Any]) -> GraphNode:
    return GraphNode(
        id=str(record["af_id"]),
        labels=tuple(record.get("labels", ())),
        properties=dict(record.get("properties", {})),
    )


def _record_to_edge(record: dict[str, Any]) -> GraphEdge:
    return GraphEdge(
        src=str(record["src"]),
        dst=str(record["dst"]),
        edge_type=str(record["edge_type"]),
        properties=dict(record.get("properties", {})),
    )


async def _walk_match_clientside(
    store: SurrealGraphStore, pattern: GraphPattern, limit: int
) -> list[Path]:
    """Pattern-match by walking the edge table client-side.

    For each segment we filter the candidate edges by type / direction
    and verify both endpoints satisfy the requested label and node
    property filters. Quadratic in graph size for long paths but
    acceptable for v0.1 — the conformance suite tests single-segment
    patterns and the limit caps the result set early.
    """
    seg0 = pattern.segments[0]
    nf0 = pattern.node_filters[0] if pattern.node_filters else {}

    # Pull all candidate start nodes that match seg0's source-side
    # constraints (label + property filters).
    all_nodes_rows = await store._r.query(_SELECT_ALL_NODES)
    starts = [
        _record_to_node(r)
        for r in _flatten(all_nodes_rows)
        if _node_matches(_record_to_node(r), seg0.src_label, nf0)
    ]

    results: list[Path] = []
    for start in starts:
        await _walk_segment(
            store=store,
            pattern=pattern,
            seg_idx=0,
            visited_nodes=[start],
            visited_edges=[],
            results=results,
            limit=limit,
        )
        if len(results) >= limit:
            break
    return results[:limit]


async def _walk_segment(
    *,
    store: SurrealGraphStore,
    pattern: GraphPattern,
    seg_idx: int,
    visited_nodes: list[GraphNode],
    visited_edges: list[GraphEdge],
    results: list[Path],
    limit: int,
) -> None:
    if seg_idx == len(pattern.segments):
        results.append(Path(nodes=tuple(visited_nodes), edges=tuple(visited_edges)))
        return
    if len(results) >= limit:
        return
    seg = pattern.segments[seg_idx]
    next_filter = pattern.node_filters[seg_idx + 1] if pattern.node_filters else {}
    candidate_edges = await store.get_edges(
        visited_nodes[-1].id,
        edge_type=seg.edge_type,
        direction=seg.direction,
    )
    for edge in candidate_edges:
        other_id = edge.dst if edge.src == visited_nodes[-1].id else edge.src
        other = await store.get_node(other_id)
        if other is None:
            continue
        if not _node_matches(other, seg.dst_label, next_filter):
            continue
        await _walk_segment(
            store=store,
            pattern=pattern,
            seg_idx=seg_idx + 1,
            visited_nodes=[*visited_nodes, other],
            visited_edges=[*visited_edges, edge],
            results=results,
            limit=limit,
        )
        if len(results) >= limit:
            return


async def _bfs_traverse(
    store: SurrealGraphStore,
    start: GraphNode,
    edge_types: tuple[str, ...] | None,
    max_depth: int,
    limit: int,
) -> list[Path]:
    results: list[Path] = []
    frontier: deque[tuple[GraphNode, list[GraphNode], list[GraphEdge]]] = deque(
        [(start, [start], [])]
    )
    while frontier and len(results) < limit:
        current, path_nodes, path_edges = frontier.popleft()
        if len(path_edges) >= max_depth:
            continue
        edges = await store.get_edges(current.id, direction="out")
        for edge in edges:
            if edge_types is not None and edge.edge_type not in edge_types:
                continue
            target = await store.get_node(edge.dst)
            if target is None:
                continue
            if any(n.id == target.id for n in path_nodes):
                continue
            new_nodes = [*path_nodes, target]
            new_edges = [*path_edges, edge]
            results.append(Path(nodes=tuple(new_nodes), edges=tuple(new_edges)))
            if len(results) >= limit:
                break
            frontier.append((target, new_nodes, new_edges))
    return results[:limit]


def _node_matches(
    node: GraphNode,
    label: str | None,
    properties_filter: dict[str, Any],
) -> bool:
    if label is not None and label not in node.labels:
        return False
    return all(node.properties.get(k) == v for k, v in properties_filter.items())


__all__ = ["SurrealGraphStore"]
