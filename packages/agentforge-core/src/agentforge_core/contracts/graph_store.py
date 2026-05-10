"""`GraphStore` — locked graph-traversal ABC.

A graph store is distinct from `MemoryStore` (claim audit log) and
`VectorStore` (similarity search): the shapes don't unify cleanly.
`MemoryStore` filters by structured metadata; `VectorStore` ranks by
cosine similarity; `GraphStore` walks relationships — multi-hop
queries, pattern matching, ontology traversal. Forcing graph traversal
into either of the existing ABCs would degrade them; keeping
`GraphStore` separate respects the contract layer's purpose (one ABC
per concern, not one per backend).

Per ADR-0007 the surface is locked at v0.1: adding a method is a
major version bump. Optional capabilities (e.g. native Cypher
support, transactions, embedded vector search) layer the same way as
`LLMClient` capabilities — declared via `capabilities()` and gated via
`supports()`.

Conformance: every shipped or third-party driver must pass
`agentforge_core.testing.run_graph_conformance` (lands alongside this
contract).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    Path,
)


class GraphStore(ABC):
    """Provider-agnostic property graph.

    Implementations:
      - treat `add_node` and `add_edge` as idempotent upserts
        (re-adding the same `id` / `(src, dst, edge_type)` replaces
        the prior record's `properties`)
      - reject edges whose `src` or `dst` references an unknown node —
        callers must `add_node` first; this keeps the graph
        well-formed and matches Cypher / SurrealQL behaviour
      - return `Path` results with `len(edges) == len(nodes) - 1` and
        edges in chain order

    Cross-driver invariants enforced by the conformance suite:
      - round-trip: `add_node(N); get_node(N.id)` returns an equal node
      - edge readback: `add_edge(E); get_edges(E.src)` includes E
      - pattern match: a one-segment pattern returns paths of length 2
      - traversal: depth-bounded BFS does not exceed `max_depth`
      - cascade delete: `delete_node(id, cascade=True)` removes
        adjacent edges; `cascade=False` raises if edges remain
    """

    @abstractmethod
    async def add_node(self, node: GraphNode) -> None:
        """Insert or replace `node` (idempotent upsert by `node.id`)."""

    @abstractmethod
    async def add_edge(self, edge: GraphEdge) -> None:
        """Insert or replace `edge` (idempotent upsert by
        `(src, dst, edge_type)`).

        Raises:
            ValueError: `edge.src` or `edge.dst` references an unknown
                node. Callers must add nodes before edges.
        """

    @abstractmethod
    async def get_node(self, node_id: str) -> GraphNode | None:
        """Return the node with this id, or `None` if absent."""

    @abstractmethod
    async def get_edges(
        self,
        node_id: str,
        *,
        edge_type: str | None = None,
        direction: Literal["out", "in", "any"] = "out",
    ) -> list[GraphEdge]:
        """Return edges incident on `node_id`.

        Args:
            node_id: The node whose edges to fetch.
            edge_type: If set, only edges of this type. `None` returns
                all types.
            direction: `"out"` returns edges where `src == node_id`;
                `"in"` returns edges where `dst == node_id`; `"any"`
                returns the union.
        """

    @abstractmethod
    async def match(
        self,
        pattern: GraphPattern,
        *,
        limit: int = 50,
    ) -> list[Path]:
        """Return paths matching `pattern`, capped at `limit`.

        Drivers may evaluate the pattern via Cypher (Neo4j),
        SurrealQL (SurrealDB), or in-memory walking (the reference
        implementation). The return shape is the same.

        Raises:
            ValueError: `limit < 1`.
        """

    @abstractmethod
    async def traverse(
        self,
        start_id: str,
        *,
        edge_types: tuple[str, ...] | None = None,
        max_depth: int = 3,
        limit: int = 50,
    ) -> list[Path]:
        """Breadth-first traversal from `start_id`.

        Returns every path of length 1..`max_depth` starting from
        `start_id`, restricted to `edge_types` if given. Useful for
        knowledge-graph expansion (pull a neighbourhood for retrieval
        augmentation).

        Args:
            start_id: The seed node. If absent, returns an empty list.
            edge_types: If set, only traverse edges of these types.
            max_depth: Hop limit (>= 1).
            limit: Maximum number of paths to return (>= 1).

        Raises:
            ValueError: `max_depth < 1` or `limit < 1`.
        """

    @abstractmethod
    async def delete_node(self, node_id: str, *, cascade: bool = False) -> bool:
        """Delete a node by id. Returns True if a node was removed.

        Args:
            node_id: The node to delete.
            cascade: If True, also delete every edge incident on the
                node. If False (default) and the node still has edges,
                raises `ValueError` — drivers must not orphan edges.

        Raises:
            ValueError: `cascade=False` and the node has incident edges.
        """

    @abstractmethod
    async def delete_edge(self, src: str, dst: str, *, edge_type: str) -> bool:
        """Delete an edge by `(src, dst, edge_type)`. Returns True if
        an edge was removed.

        Unknown triples return False (no exception).
        """

    @abstractmethod
    async def close(self) -> None:
        """Release backing resources (connections, file handles)."""

    def capabilities(self) -> set[str]:
        """Optional capabilities this driver supports.

        Default empty set. Closed vocabulary (additions are minor
        bumps): `"transactions"` (multi-statement atomic writes),
        `"cypher"` (driver speaks Cypher natively),
        `"surrealql"` (driver speaks SurrealQL natively),
        `"vector"` (driver also indexes embeddings — typically also
        implements `VectorStore`), `"live_query"` (driver pushes
        change notifications), `"fulltext"` (driver indexes node /
        edge property text).
        """
        return set()

    def supports(self, capability: str) -> bool:
        """True if this driver declares the given capability."""
        return capability in self.capabilities()
