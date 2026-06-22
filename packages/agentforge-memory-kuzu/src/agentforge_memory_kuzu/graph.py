"""`KuzuGraphStore` — embedded, file-backed `GraphStore` (feat-027).

A persistent property graph in a single directory, in-process, no server
— the graph analogue of the SQLite `MemoryStore`. Implements the locked
`GraphStore` contract and passes `run_graph_conformance`.

Design notes
------------
- **Storage.** One generic node table `AfNode(id, labels, props)` and one
  generic relationship table `AfEdge(etype, props)`, created lazily on
  open. `labels` and `props` are JSON strings so arbitrary
  schemaless `GraphNode`/`GraphEdge` shapes map onto Kùzu's typed schema
  without per-shape table DDL. Upserts use Cypher `MERGE` (idempotent on
  `id` for nodes, on `(src, dst, etype)` for edges).
- **`get_node` / `get_edges`** are native Cypher.
- **`traverse` / `match`** run as Python graph algorithms over those
  native primitives — mirroring the reference `InMemoryGraphStore`. Kùzu's
  recursive-path Cypher can't take a bound parameter inside an `all(...)`
  predicate (engine assertion), and client-side traversal keeps the path
  semantics (per-hop prefixes, cycle avoidance) exactly contract-correct.
- **Concurrency.** Kùzu is embedded single-writer and its `Connection`
  isn't thread-safe; every call is dispatched to a worker thread
  (`asyncio.to_thread`, since the driver is synchronous) under an
  `asyncio.Lock` so access is serialised. Documented constraint.
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from pathlib import Path as FilePath
from typing import TYPE_CHECKING, Any

import kuzu
from agentforge_core.contracts.graph_store import GraphStore
from agentforge_core.values.graph import GraphEdge, GraphNode, GraphPattern, Path

if TYPE_CHECKING:
    from typing import Literal

_NODE_TABLE = (
    "CREATE NODE TABLE IF NOT EXISTS "
    "AfNode(id STRING, labels STRING, props STRING, PRIMARY KEY(id))"
)
_EDGE_TABLE = (
    "CREATE REL TABLE IF NOT EXISTS AfEdge(FROM AfNode TO AfNode, etype STRING, props STRING)"
)


def _exec_collect(conn: Any, query: str, params: dict[str, Any] | None) -> list[list[Any]]:
    """Execute `query` and drain its rows — runs inside a worker thread."""
    result = conn.execute(query, parameters=params) if params else conn.execute(query)
    rows: list[list[Any]] = []
    while result.has_next():
        rows.append(result.get_next())
    return rows


class KuzuGraphStore(GraphStore):
    """Embedded file-backed `GraphStore` backed by Kùzu."""

    def __init__(self, *, database: Any, connection: Any) -> None:
        self._db = database
        self._conn: Any = connection
        self._lock = asyncio.Lock()

    # -- construction --------------------------------------------------

    @classmethod
    async def from_path(cls, path: str | FilePath) -> KuzuGraphStore:
        """Open or create an embedded graph database under `path`.

        The directory is created if absent; the schema is bootstrapped on
        first open. Mirrors `SqliteMemoryStore.from_path`.
        """
        target = FilePath(path)

        def _open() -> tuple[Any, Any]:
            target.parent.mkdir(parents=True, exist_ok=True)
            database = kuzu.Database(str(target))
            connection = kuzu.Connection(database)
            connection.execute(_NODE_TABLE)
            connection.execute(_EDGE_TABLE)
            return database, connection

        database, connection = await asyncio.to_thread(_open)
        return cls(database=database, connection=connection)

    @classmethod
    async def from_config(cls, *, path: str | FilePath) -> KuzuGraphStore:
        """Build from a `config:` block (`{path: .ckg}`)."""
        return await cls.from_path(path)

    async def __aenter__(self) -> KuzuGraphStore:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def _query(self, query: str, params: dict[str, Any] | None = None) -> list[list[Any]]:
        async with self._lock:
            return await asyncio.to_thread(_exec_collect, self._conn, query, params)

    # -- writes --------------------------------------------------------

    async def add_node(self, node: GraphNode) -> None:
        await self._query(
            "MERGE (n:AfNode {id: $id}) SET n.labels = $labels, n.props = $props",
            {
                "id": node.id,
                "labels": json.dumps(list(node.labels)),
                "props": json.dumps(dict(node.properties)),
            },
        )

    async def add_edge(self, edge: GraphEdge) -> None:
        present = {
            row[0]
            for row in await self._query(
                "MATCH (n:AfNode) WHERE n.id IN $ids RETURN n.id",
                {"ids": [edge.src, edge.dst]},
            )
        }
        missing = [nid for nid in (edge.src, edge.dst) if nid not in present]
        if missing:
            msg = f"add_edge: node(s) {missing} do not exist; add them before the edge"
            raise ValueError(msg)
        await self._query(
            "MATCH (s:AfNode {id: $src}), (d:AfNode {id: $dst}) "
            "MERGE (s)-[e:AfEdge {etype: $etype}]->(d) SET e.props = $props",
            {
                "src": edge.src,
                "dst": edge.dst,
                "etype": edge.edge_type,
                "props": json.dumps(dict(edge.properties)),
            },
        )

    # -- reads ---------------------------------------------------------

    async def get_node(self, node_id: str) -> GraphNode | None:
        rows = await self._query(
            "MATCH (n:AfNode {id: $id}) RETURN n.id, n.labels, n.props",
            {"id": node_id},
        )
        if not rows:
            return None
        return _row_to_node(rows[0])

    async def get_edges(
        self,
        node_id: str,
        *,
        edge_type: str | None = None,
        direction: Literal["out", "in", "any"] = "out",
    ) -> list[GraphEdge]:
        if direction == "any":
            out = await self.get_edges(node_id, edge_type=edge_type, direction="out")
            inc = await self.get_edges(node_id, edge_type=edge_type, direction="in")
            return out + inc

        if direction == "out":
            pattern = "(anchor:AfNode {id: $id})-[e:AfEdge]->(other:AfNode)"
            ret = "anchor.id, other.id, e.etype, e.props"
        else:
            pattern = "(other:AfNode)-[e:AfEdge]->(anchor:AfNode {id: $id})"
            ret = "other.id, anchor.id, e.etype, e.props"
        where = " WHERE e.etype = $etype" if edge_type is not None else ""
        params: dict[str, Any] = {"id": node_id}
        if edge_type is not None:
            params["etype"] = edge_type
        rows = await self._query(f"MATCH {pattern}{where} RETURN {ret}", params)
        return [_row_to_edge(row) for row in rows]

    async def traverse(
        self,
        start_id: str,
        *,
        edge_types: tuple[str, ...] | None = None,
        max_depth: int = 3,
        limit: int = 50,
    ) -> list[Path]:
        if max_depth < 1:
            raise ValueError(f"max_depth must be >= 1, got {max_depth}")
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        start = await self.get_node(start_id)
        if start is None:
            return []

        results: list[Path] = []
        frontier: deque[tuple[str, list[GraphNode], list[GraphEdge]]] = deque(
            [(start_id, [start], [])]
        )
        while frontier and len(results) < limit:
            current, path_nodes, path_edges = frontier.popleft()
            if len(path_edges) >= max_depth:
                continue
            for edge in await self.get_edges(current, direction="out"):
                if edge_types is not None and edge.edge_type not in edge_types:
                    continue
                target = await self.get_node(edge.dst)
                if target is None:
                    continue
                if any(n.id == target.id for n in path_nodes):
                    continue  # cycle avoidance — don't revisit a node in this path
                new_nodes = [*path_nodes, target]
                new_edges = [*path_edges, edge]
                results.append(Path(nodes=tuple(new_nodes), edges=tuple(new_edges)))
                if len(results) >= limit:
                    break
                frontier.append((target.id, new_nodes, new_edges))
        return results[:limit]

    async def match(self, pattern: GraphPattern, *, limit: int = 50) -> list[Path]:
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        node_filters = pattern.node_filters
        seg0 = pattern.segments[0]
        filt0 = node_filters[0] if node_filters else None

        all_nodes = [
            _row_to_node(row)
            for row in await self._query("MATCH (n:AfNode) RETURN n.id, n.labels, n.props")
        ]
        results: list[Path] = []
        for node in all_nodes:
            if len(results) >= limit:
                break
            if _node_matches(node, seg0.src_label, filt0):
                await self._walk(node, pattern, 0, [node], [], results, limit)
        return results[:limit]

    async def _walk(
        self,
        current: GraphNode,
        pattern: GraphPattern,
        seg_index: int,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        results: list[Path],
        limit: int,
    ) -> None:
        if len(results) >= limit:
            return
        if seg_index == len(pattern.segments):
            results.append(Path(nodes=tuple(nodes), edges=tuple(edges)))
            return
        seg = pattern.segments[seg_index]
        next_filter = pattern.node_filters[seg_index + 1] if pattern.node_filters else None
        for edge in await self.get_edges(
            current.id, edge_type=seg.edge_type, direction=seg.direction
        ):
            other_id = edge.dst if edge.src == current.id else edge.src
            other = await self.get_node(other_id)
            if other is None or not _node_matches(other, seg.dst_label, next_filter):
                continue
            await self._walk(
                other, pattern, seg_index + 1, [*nodes, other], [*edges, edge], results, limit
            )
            if len(results) >= limit:
                return

    # -- deletes -------------------------------------------------------

    async def delete_node(self, node_id: str, *, cascade: bool = False) -> bool:
        exists = await self._query("MATCH (n:AfNode {id: $id}) RETURN n.id", {"id": node_id})
        if not exists:
            return False
        counted = await self._query(
            "MATCH (n:AfNode {id: $id})-[e:AfEdge]-(:AfNode) RETURN count(e)",
            {"id": node_id},
        )
        incident = int(counted[0][0]) if counted else 0
        if incident and not cascade:
            msg = (
                f"delete_node: {node_id!r} has {incident} incident edge(s); "
                f"pass cascade=True to remove them"
            )
            raise ValueError(msg)
        clause = "DETACH DELETE n" if cascade else "DELETE n"
        await self._query(f"MATCH (n:AfNode {{id: $id}}) {clause}", {"id": node_id})
        return True

    async def delete_edge(self, src: str, dst: str, *, edge_type: str) -> bool:
        match_clause = (
            "MATCH (s:AfNode {id: $src})-[e:AfEdge {etype: $etype}]->(d:AfNode {id: $dst})"
        )
        params = {"src": src, "dst": dst, "etype": edge_type}
        counted = await self._query(f"{match_clause} RETURN count(e)", params)
        if not counted or int(counted[0][0]) == 0:
            return False
        await self._query(f"{match_clause} DELETE e", params)
        return True

    # -- capabilities / lifecycle -------------------------------------

    def capabilities(self) -> set[str]:
        return {"cypher"}

    async def close(self) -> None:
        async with self._lock:
            conn, self._conn = self._conn, None
            database, self._db = self._db, None

            def _shutdown() -> None:
                for closeable in (conn, database):
                    closer = getattr(closeable, "close", None)
                    if callable(closer):
                        closer()

            await asyncio.to_thread(_shutdown)


def _row_to_node(row: list[Any]) -> GraphNode:
    return GraphNode(
        id=row[0],
        labels=tuple(json.loads(row[1]) if row[1] else []),
        properties=json.loads(row[2]) if row[2] else {},
    )


def _row_to_edge(row: list[Any]) -> GraphEdge:
    return GraphEdge(
        src=row[0],
        dst=row[1],
        edge_type=row[2],
        properties=json.loads(row[3]) if row[3] else {},
    )


def _node_matches(node: GraphNode, label: str | None, props: dict[str, Any] | None) -> bool:
    if label is not None and label not in node.labels:
        return False
    if props:
        return all(node.properties.get(key) == value for key, value in props.items())
    return True


__all__ = ["KuzuGraphStore"]
