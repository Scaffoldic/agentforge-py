"""`InMemoryGraphStore` — process-local `GraphStore` reference impl.

Plain dict of nodes plus an adjacency list. Suitable for tests, demos,
and small knowledge graphs (~thousands of nodes). Production
deployments swap to `agentforge-memory-neo4j` or
`agentforge-memory-surrealdb` — both pass the same
`run_graph_conformance` suite.

Design notes:
  - All operations are O(degree) or smaller; pattern matching iterates
    edges. Fine for small graphs, sluggish past tens of thousands of
    edges. Native graph DBs declare richer capabilities (`"cypher"`,
    `"transactions"`); this one does not.
  - Idempotent upserts: re-adding a node or edge replaces its
    properties. The contract requires this for both shapes.
  - Edges that would orphan are blocked by `delete_node(cascade=False)`.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from typing import Any, Literal

from agentforge_core.contracts.graph_store import GraphStore
from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    GraphSegment,
    Path,
)


class InMemoryGraphStore(GraphStore):
    """In-process `GraphStore` backed by dicts + adjacency lists."""

    def __init__(self) -> None:
        self._nodes: OrderedDict[str, GraphNode] = OrderedDict()
        # Outgoing edges keyed by src; ordered for determinism.
        self._out: dict[str, list[GraphEdge]] = {}
        # Incoming edges keyed by dst; same ordering.
        self._in: dict[str, list[GraphEdge]] = {}

    async def add_node(self, node: GraphNode) -> None:
        self._nodes[node.id] = node
        self._out.setdefault(node.id, [])
        self._in.setdefault(node.id, [])

    async def add_edge(self, edge: GraphEdge) -> None:
        if edge.src not in self._nodes:
            msg = f"add_edge: source node {edge.src!r} does not exist"
            raise ValueError(msg)
        if edge.dst not in self._nodes:
            msg = f"add_edge: destination node {edge.dst!r} does not exist"
            raise ValueError(msg)
        # Idempotent on (src, dst, edge_type): replace existing entry.
        self._out[edge.src] = [
            e
            for e in self._out[edge.src]
            if not (e.dst == edge.dst and e.edge_type == edge.edge_type)
        ]
        self._in[edge.dst] = [
            e
            for e in self._in[edge.dst]
            if not (e.src == edge.src and e.edge_type == edge.edge_type)
        ]
        self._out[edge.src].append(edge)
        self._in[edge.dst].append(edge)

    async def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    async def get_edges(
        self,
        node_id: str,
        *,
        edge_type: str | None = None,
        direction: Literal["out", "in", "any"] = "out",
    ) -> list[GraphEdge]:
        if node_id not in self._nodes:
            return []
        candidates: list[GraphEdge]
        if direction == "out":
            candidates = list(self._out.get(node_id, ()))
        elif direction == "in":
            candidates = list(self._in.get(node_id, ()))
        else:
            candidates = [*self._out.get(node_id, ()), *self._in.get(node_id, ())]
        if edge_type is not None:
            candidates = [e for e in candidates if e.edge_type == edge_type]
        return candidates

    async def match(self, pattern: GraphPattern, *, limit: int = 50) -> list[Path]:
        if limit < 1:
            msg = f"limit must be >= 1, got {limit}"
            raise ValueError(msg)

        # Seed with every node — drivers like Neo4j let the optimiser
        # pick a driving node; we walk all candidates that satisfy the
        # first segment's source label + node filter.
        seg0 = pattern.segments[0]
        node_filter0 = pattern.node_filters[0] if pattern.node_filters else {}
        starts = [n for n in self._nodes.values() if _node_matches(n, seg0.src_label, node_filter0)]

        results: list[Path] = []
        for start in starts:
            self._walk_pattern(
                start=start,
                pattern=pattern,
                seg_index=0,
                visited_nodes=[start],
                visited_edges=[],
                results=results,
                limit=limit,
            )
            if len(results) >= limit:
                break
        return results[:limit]

    def _walk_pattern(
        self,
        *,
        start: GraphNode,
        pattern: GraphPattern,
        seg_index: int,
        visited_nodes: list[GraphNode],
        visited_edges: list[GraphEdge],
        results: list[Path],
        limit: int,
    ) -> None:
        if seg_index == len(pattern.segments):
            results.append(Path(nodes=tuple(visited_nodes), edges=tuple(visited_edges)))
            return
        if len(results) >= limit:
            return

        seg = pattern.segments[seg_index]
        next_filter = pattern.node_filters[seg_index + 1] if pattern.node_filters else {}
        for edge in self._edges_for_segment(start.id, seg):
            other_id = edge.dst if edge.src == start.id else edge.src
            other = self._nodes.get(other_id)
            if other is None:
                continue
            if not _node_matches(other, seg.dst_label, next_filter):
                continue
            self._walk_pattern(
                start=other,
                pattern=pattern,
                seg_index=seg_index + 1,
                visited_nodes=[*visited_nodes, other],
                visited_edges=[*visited_edges, edge],
                results=results,
                limit=limit,
            )
            if len(results) >= limit:
                return

    def _edges_for_segment(self, node_id: str, seg: GraphSegment) -> list[GraphEdge]:
        edges: list[GraphEdge]
        if seg.direction == "out":
            edges = list(self._out.get(node_id, ()))
        elif seg.direction == "in":
            edges = list(self._in.get(node_id, ()))
        else:
            edges = [*self._out.get(node_id, ()), *self._in.get(node_id, ())]
        if seg.edge_type is not None:
            edges = [e for e in edges if e.edge_type == seg.edge_type]
        return edges

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
        if start_id not in self._nodes:
            return []

        start_node = self._nodes[start_id]
        results: list[Path] = []
        # BFS frontier of (current_node, path-so-far-nodes, path-so-far-edges)
        frontier: deque[tuple[str, list[GraphNode], list[GraphEdge]]] = deque(
            [(start_id, [start_node], [])]
        )
        while frontier and len(results) < limit:
            current, path_nodes, path_edges = frontier.popleft()
            if len(path_edges) >= max_depth:
                continue
            for edge in self._out.get(current, ()):
                if edge_types is not None and edge.edge_type not in edge_types:
                    continue
                target = self._nodes.get(edge.dst)
                if target is None:
                    continue
                # Avoid cycles: don't revisit a node already in this path.
                if any(n.id == target.id for n in path_nodes):
                    continue
                new_nodes = [*path_nodes, target]
                new_edges = [*path_edges, edge]
                results.append(Path(nodes=tuple(new_nodes), edges=tuple(new_edges)))
                if len(results) >= limit:
                    break
                frontier.append((target.id, new_nodes, new_edges))
        return results[:limit]

    async def delete_node(self, node_id: str, *, cascade: bool = False) -> bool:
        if node_id not in self._nodes:
            return False
        outgoing = self._out.get(node_id, [])
        incoming = self._in.get(node_id, [])
        if not cascade and (outgoing or incoming):
            msg = (
                f"delete_node: {node_id!r} has {len(outgoing) + len(incoming)} "
                f"incident edge(s); pass cascade=True to remove them"
            )
            raise ValueError(msg)
        # Cascade removes incident edges from the *other* side too.
        for e in list(outgoing):
            self._in[e.dst] = [x for x in self._in[e.dst] if x is not e]
        for e in list(incoming):
            self._out[e.src] = [x for x in self._out[e.src] if x is not e]
        self._out.pop(node_id, None)
        self._in.pop(node_id, None)
        self._nodes.pop(node_id, None)
        return True

    async def delete_edge(self, src: str, dst: str, *, edge_type: str) -> bool:
        out = self._out.get(src, [])
        match = next((e for e in out if e.dst == dst and e.edge_type == edge_type), None)
        if match is None:
            return False
        self._out[src] = [e for e in out if e is not match]
        self._in[dst] = [e for e in self._in.get(dst, ()) if e is not match]
        return True

    async def close(self) -> None:
        self._nodes.clear()
        self._out.clear()
        self._in.clear()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _node_matches(
    node: GraphNode,
    label: str | None,
    properties_filter: dict[str, Any],
) -> bool:
    if label is not None and label not in node.labels:
        return False
    return all(node.properties.get(k) == v for k, v in properties_filter.items())
