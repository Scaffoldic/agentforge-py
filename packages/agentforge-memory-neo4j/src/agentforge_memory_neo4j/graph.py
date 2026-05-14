"""`Neo4jGraphStore` — `GraphStore` over Neo4j via the official
`neo4j` async driver.

Mapping strategy:
  - Every node carries the marker label `:AfNode` (so we can MATCH
    everything in the store) plus a `_af_labels` property holding the
    user-declared labels tuple. Cypher cannot parameterise label
    names in MATCH/MERGE; the marker-label-plus-property pattern is
    the standard workaround for dynamic label vocabularies.
  - Every edge carries the marker relationship type `:AF_EDGE` plus an
    `_af_edge_type` property. Same reasoning as node labels.
  - Every node carries an `_af_id` property as the framework-level id
    (Neo4j's internal element_id is unstable across rewrites).

Schema bootstrap (`init_schema`) creates uniqueness + lookup indexes
for `_af_id` on `:AfNode` and `_af_edge_type` on `:AF_EDGE`.

Capabilities: `{"transactions", "cypher", "fulltext"}` — every write
is wrapped in `session.execute_write`; reads in `execute_read`.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Literal

from agentforge_core.contracts.graph_store import GraphStore
from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    Path,
)
from neo4j import AsyncGraphDatabase

from agentforge_memory_neo4j._migrator import Neo4jMigrator
from agentforge_memory_neo4j._runner import CypherRunner, _Neo4jDriverRunner

_NODE_LABEL = "AfNode"
_EDGE_TYPE = "AF_EDGE"
_ID_PROP = "_af_id"
_LABELS_PROP = "_af_labels"
_EDGE_TYPE_PROP = "_af_edge_type"

_INIT_SCHEMA_CYPHER = (
    f"CREATE CONSTRAINT af_node_id IF NOT EXISTS "
    f"FOR (n:{_NODE_LABEL}) REQUIRE n.{_ID_PROP} IS UNIQUE",
    f"CREATE INDEX af_node_labels IF NOT EXISTS FOR (n:{_NODE_LABEL}) ON (n.{_LABELS_PROP})",
    f"CREATE INDEX af_edge_type IF NOT EXISTS FOR ()-[r:{_EDGE_TYPE}]-() ON (r.{_EDGE_TYPE_PROP})",
)


class Neo4jGraphStore(GraphStore):
    """`GraphStore` over Neo4j.

    Construct via `from_url` for ergonomic use; the bare constructor
    accepts an injected `CypherRunner` so unit tests can fake the
    driver without spinning up Neo4j.
    """

    def __init__(self, *, runner: CypherRunner) -> None:
        self._r = runner

    # ------------------------------------------------------------------
    # Construction / lifecycle
    # ------------------------------------------------------------------

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        auth: tuple[str, str],
        database: str = "neo4j",
    ) -> Neo4jGraphStore:
        """Open a Neo4j connection and return a graph store."""
        driver = AsyncGraphDatabase.driver(url, auth=auth)
        return cls(runner=_Neo4jDriverRunner(driver, database))

    async def __aenter__(self) -> Neo4jGraphStore:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    def migrator(self) -> Neo4jMigrator:
        """Return a `Neo4jMigrator` configured against the package's
        bundled migrations directory (feat-024)."""
        return Neo4jMigrator(self._r)

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
        cypher = (
            f"MERGE (n:{_NODE_LABEL} {{{_ID_PROP}: $id}}) "
            f"SET n = $properties "
            f"SET n.{_ID_PROP} = $id, n.{_LABELS_PROP} = $labels"
        )
        await self._r.execute_write(
            cypher,
            {
                "id": node.id,
                "properties": dict(node.properties),
                "labels": list(node.labels),
            },
        )

    async def add_edge(self, edge: GraphEdge) -> None:
        # Verify endpoints exist — the contract requires ValueError
        # rather than silent missing-endpoint creation.
        rows = await self._r.execute_read(
            f"MATCH (s:{_NODE_LABEL} {{{_ID_PROP}: $src}}) "
            f"MATCH (d:{_NODE_LABEL} {{{_ID_PROP}: $dst}}) "
            "RETURN s, d",
            {"src": edge.src, "dst": edge.dst},
        )
        if not rows:
            present = await self._r.execute_read(
                f"MATCH (n:{_NODE_LABEL}) WHERE n.{_ID_PROP} IN $ids RETURN n.{_ID_PROP} AS id",
                {"ids": [edge.src, edge.dst]},
            )
            present_ids = {r["id"] for r in present}
            missing = (
                [edge.src, edge.dst]
                if not present_ids
                else ([edge.src] if edge.src not in present_ids else [edge.dst])
            )
            msg = f"add_edge: node(s) {missing!r} do not exist"
            raise ValueError(msg)

        cypher = (
            f"MATCH (s:{_NODE_LABEL} {{{_ID_PROP}: $src}}) "
            f"MATCH (d:{_NODE_LABEL} {{{_ID_PROP}: $dst}}) "
            f"MERGE (s)-[r:{_EDGE_TYPE} {{{_EDGE_TYPE_PROP}: $edge_type}}]->(d) "
            f"SET r = $properties "
            f"SET r.{_EDGE_TYPE_PROP} = $edge_type"
        )
        await self._r.execute_write(
            cypher,
            {
                "src": edge.src,
                "dst": edge.dst,
                "edge_type": edge.edge_type,
                "properties": dict(edge.properties),
            },
        )

    async def get_node(self, node_id: str) -> GraphNode | None:
        rows = await self._r.execute_read(
            f"MATCH (n:{_NODE_LABEL} {{{_ID_PROP}: $id}}) RETURN n",
            {"id": node_id},
        )
        if not rows:
            return None
        return _row_to_node(rows[0]["n"])

    async def get_edges(
        self,
        node_id: str,
        *,
        edge_type: str | None = None,
        direction: Literal["out", "in", "any"] = "out",
    ) -> list[GraphEdge]:
        if direction == "out":
            pattern = (
                f"(n:{_NODE_LABEL} {{{_ID_PROP}: $id}})-[r:{_EDGE_TYPE}]->(other:{_NODE_LABEL})"
            )
            return await self._collect_edges(pattern, node_id, edge_type, src_is_n=True)
        if direction == "in":
            pattern = (
                f"(n:{_NODE_LABEL} {{{_ID_PROP}: $id}})<-[r:{_EDGE_TYPE}]-(other:{_NODE_LABEL})"
            )
            return await self._collect_edges(pattern, node_id, edge_type, src_is_n=False)
        # Fall through: direction is "any" — union of out and in.
        out = await self.get_edges(node_id, edge_type=edge_type, direction="out")
        inn = await self.get_edges(node_id, edge_type=edge_type, direction="in")
        return out + inn

    async def _collect_edges(
        self, pattern: str, node_id: str, edge_type: str | None, *, src_is_n: bool
    ) -> list[GraphEdge]:
        where = f"WHERE r.{_EDGE_TYPE_PROP} = $edge_type " if edge_type is not None else ""
        n_id = f"n.{_ID_PROP}"
        other_id = f"other.{_ID_PROP}"
        src_expr = n_id if src_is_n else other_id
        dst_expr = other_id if src_is_n else n_id
        cypher = f"MATCH {pattern} {where}RETURN {src_expr} AS src, {dst_expr} AS dst, r"
        params: dict[str, Any] = {"id": node_id}
        if edge_type is not None:
            params["edge_type"] = edge_type
        rows = await self._r.execute_read(cypher, params)
        return [_row_to_edge(row["src"], row["dst"], row["r"]) for row in rows]

    async def match(self, pattern: GraphPattern, *, limit: int = 50) -> list[Path]:
        if limit < 1:
            msg = f"limit must be >= 1, got {limit}"
            raise ValueError(msg)

        cypher, params = _compile_match(pattern, limit)
        rows = await self._r.execute_read(cypher, params)
        return [_row_to_path(row, n_segments=len(pattern.segments)) for row in rows]

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

        # Verify start exists; absent → empty (contract).
        start_rows = await self._r.execute_read(
            f"MATCH (n:{_NODE_LABEL} {{{_ID_PROP}: $id}}) RETURN n",
            {"id": start_id},
        )
        if not start_rows:
            return []

        # Cypher requires an integer literal for path length, not a
        # parameter. We've validated max_depth >= 1 above, so it is
        # safe to interpolate.
        cypher = (
            f"MATCH path = (start:{_NODE_LABEL} {{{_ID_PROP}: $start_id}})"
            f"-[r:{_EDGE_TYPE}*1..{int(max_depth)}]->(end:{_NODE_LABEL}) "
        )
        if edge_types is not None:
            cypher += f"WHERE all(rel IN r WHERE rel.{_EDGE_TYPE_PROP} IN $edge_types) "
        cypher += "RETURN path LIMIT $limit"

        params: dict[str, Any] = {"start_id": start_id, "limit": limit}
        if edge_types is not None:
            params["edge_types"] = list(edge_types)

        rows = await self._r.execute_read(cypher, params)
        return [_path_record_to_path(row["path"]) for row in rows]

    async def delete_node(self, node_id: str, *, cascade: bool = False) -> bool:
        # Check existence first — a no-op delete returns False.
        present = await self._r.execute_read(
            f"MATCH (n:{_NODE_LABEL} {{{_ID_PROP}: $id}}) RETURN count(n) AS c",
            {"id": node_id},
        )
        if not present or present[0]["c"] == 0:
            return False

        # Edges incident on the node: cascade or fail.
        edges = await self._r.execute_read(
            f"MATCH (n:{_NODE_LABEL} {{{_ID_PROP}: $id}})-[r:{_EDGE_TYPE}]-() RETURN count(r) AS c",
            {"id": node_id},
        )
        edge_count = edges[0]["c"] if edges else 0
        if edge_count > 0 and not cascade:
            msg = (
                f"delete_node: {node_id!r} has {edge_count} incident edge(s); "
                "pass cascade=True to remove them"
            )
            raise ValueError(msg)

        if cascade:
            await self._r.execute_write(
                f"MATCH (n:{_NODE_LABEL} {{{_ID_PROP}: $id}}) DETACH DELETE n",
                {"id": node_id},
            )
        else:
            await self._r.execute_write(
                f"MATCH (n:{_NODE_LABEL} {{{_ID_PROP}: $id}}) DELETE n",
                {"id": node_id},
            )
        return True

    async def delete_edge(self, src: str, dst: str, *, edge_type: str) -> bool:
        rows = await self._r.execute_write(
            f"MATCH (s:{_NODE_LABEL} {{{_ID_PROP}: $src}})"
            f"-[r:{_EDGE_TYPE} {{{_EDGE_TYPE_PROP}: $edge_type}}]->"
            f"(d:{_NODE_LABEL} {{{_ID_PROP}: $dst}}) "
            "WITH r LIMIT 1 "
            "DELETE r RETURN count(r) AS c",
            {"src": src, "dst": dst, "edge_type": edge_type},
        )
        if not rows:
            return False
        return bool(rows[0]["c"])

    def capabilities(self) -> set[str]:
        return {"transactions", "cypher", "fulltext"}


# ----------------------------------------------------------------------
# Compilers (Cypher generation for `match`)
# ----------------------------------------------------------------------


def _compile_match(pattern: GraphPattern, limit: int) -> tuple[str, dict[str, Any]]:
    """Compose a parameterised Cypher MATCH for the chained pattern.

    Returns (cypher, params). The query yields one row per matching
    path with keys `n0..nN` (nodes) and `r0..r{N-1}` (relationships)
    in chain order.
    """
    parts: list[str] = []
    where: list[str] = []
    params: dict[str, Any] = {"limit": limit}

    # Node 0
    parts.append(f"(n0:{_NODE_LABEL})")
    _emit_node_filter(
        0, pattern.segments[0].src_label, pattern.node_filters, where=where, params=params
    )

    for i, seg in enumerate(pattern.segments):
        rel_var = f"r{i}"
        next_node_var = f"n{i + 1}"
        if seg.direction == "out":
            parts.append(f"-[{rel_var}:{_EDGE_TYPE}]->({next_node_var}:{_NODE_LABEL})")
        elif seg.direction == "in":
            parts.append(f"<-[{rel_var}:{_EDGE_TYPE}]-({next_node_var}:{_NODE_LABEL})")
        else:  # "any"
            parts.append(f"-[{rel_var}:{_EDGE_TYPE}]-({next_node_var}:{_NODE_LABEL})")
        if seg.edge_type is not None:
            param_key = f"edge_type_{i}"
            where.append(f"{rel_var}.{_EDGE_TYPE_PROP} = ${param_key}")
            params[param_key] = seg.edge_type
        _emit_node_filter(i + 1, seg.dst_label, pattern.node_filters, where=where, params=params)

    cypher = "MATCH " + "".join(parts)
    if where:
        cypher += " WHERE " + " AND ".join(where)
    return_items = ", ".join(f"n{i}" for i in range(len(pattern.segments) + 1))
    return_items += ", " + ", ".join(f"r{i}" for i in range(len(pattern.segments)))
    cypher += f" RETURN {return_items} LIMIT $limit"
    return cypher, params


def _emit_node_filter(
    pos: int,
    label: str | None,
    node_filters: tuple[dict[str, Any], ...],
    *,
    where: list[str],
    params: dict[str, Any],
) -> None:
    """Append node-level WHERE clauses for label + property filters."""
    var = f"n{pos}"
    if label is not None:
        param_key = f"label_{pos}"
        where.append(f"${param_key} IN {var}.{_LABELS_PROP}")
        params[param_key] = label
    if node_filters and pos < len(node_filters):
        for k, v in node_filters[pos].items():
            param_key = f"prop_{pos}_{k}"
            where.append(f"{var}.{k} = ${param_key}")
            params[param_key] = v


# ----------------------------------------------------------------------
# Decoders (neo4j Record → framework value types)
# ----------------------------------------------------------------------


def _row_to_node(record_node: Any) -> GraphNode:
    """Convert a neo4j Node record into a `GraphNode`.

    `record_node` quacks like a mapping (`__getitem__`, `keys()`); the
    fake runner returns a plain dict and the real driver returns
    `neo4j.graph.Node`, both of which support that interface.
    """
    props = dict(record_node)
    node_id = props.pop(_ID_PROP)
    labels = tuple(props.pop(_LABELS_PROP, ()))
    return GraphNode(id=str(node_id), labels=labels, properties=props)


def _row_to_edge(src: Any, dst: Any, record_rel: Any) -> GraphEdge:
    """Convert (src_id, dst_id, relationship-record) into a `GraphEdge`."""
    props = dict(record_rel)
    edge_type = props.pop(_EDGE_TYPE_PROP)
    return GraphEdge(
        src=str(src),
        dst=str(dst),
        edge_type=str(edge_type),
        properties=props,
    )


def _row_to_path(row: dict[str, Any], *, n_segments: int) -> Path:
    """Reconstruct a `Path` from a row of n0..nN, r0..r{N-1} columns."""
    nodes = tuple(_row_to_node(row[f"n{i}"]) for i in range(n_segments + 1))
    edges = tuple(
        _row_to_edge(nodes[i].id, nodes[i + 1].id, row[f"r{i}"]) for i in range(n_segments)
    )
    return Path(nodes=nodes, edges=edges)


def _path_record_to_path(record_path: Any) -> Path:
    """Convert a neo4j Path record into a framework `Path`.

    The neo4j path object exposes `.nodes` (list[Node]) and
    `.relationships` (list[Relationship]). The fake runner returns a
    dict-shaped equivalent.
    """
    raw_nodes = (
        list(record_path.nodes) if hasattr(record_path, "nodes") else list(record_path["nodes"])
    )
    raw_rels = (
        list(record_path.relationships)
        if hasattr(record_path, "relationships")
        else list(record_path["relationships"])
    )
    nodes = tuple(_row_to_node(n) for n in raw_nodes)
    edges = tuple(
        _row_to_edge(nodes[i].id, nodes[i + 1].id, raw_rels[i]) for i in range(len(raw_rels))
    )
    return Path(nodes=nodes, edges=edges)


__all__ = ["Neo4jGraphStore"]
