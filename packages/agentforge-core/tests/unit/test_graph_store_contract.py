"""Unit tests for the `GraphStore` ABC default behaviours.

The ABC itself is abstract, so most behaviour testing happens via the
conformance suite against concrete drivers. Here we cover the
default-method behaviours that don't require a concrete impl.
"""

from __future__ import annotations

from typing import Literal

import pytest
from agentforge_core.contracts.graph_store import GraphStore
from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    Path,
)


class _MinimalStore(GraphStore):
    """Minimal concrete impl with no extra capabilities."""

    async def add_node(self, node: GraphNode) -> None: ...
    async def add_edge(self, edge: GraphEdge) -> None: ...

    async def get_node(self, node_id: str) -> GraphNode | None:
        return None

    async def get_edges(
        self,
        node_id: str,
        *,
        edge_type: str | None = None,
        direction: Literal["out", "in", "any"] = "out",
    ) -> list[GraphEdge]:
        return []

    async def match(self, pattern: GraphPattern, *, limit: int = 50) -> list[Path]:
        return []

    async def traverse(
        self,
        start_id: str,
        *,
        edge_types: tuple[str, ...] | None = None,
        max_depth: int = 3,
        limit: int = 50,
    ) -> list[Path]:
        return []

    async def delete_node(self, node_id: str, *, cascade: bool = False) -> bool:
        return False

    async def delete_edge(self, src: str, dst: str, *, edge_type: str) -> bool:
        return False

    async def close(self) -> None: ...


class _CypherStore(_MinimalStore):
    """Driver that declares Cypher + transactions support."""

    def capabilities(self) -> set[str]:
        return {"cypher", "transactions"}


# ---- Default capabilities ----


def test_default_store_declares_no_capabilities() -> None:
    store = _MinimalStore()
    assert store.capabilities() == set()
    assert store.supports("cypher") is False
    assert store.supports("anything") is False


def test_cypher_store_declares_capabilities() -> None:
    store = _CypherStore()
    assert store.supports("cypher") is True
    assert store.supports("transactions") is True
    # Capabilities not declared are still False.
    assert store.supports("surrealql") is False
    assert store.supports("vector") is False


def test_supports_unknown_capability_is_false() -> None:
    """Per ADR-0009, supports() is honest about unknowns — never
    optimistically True for capabilities the driver hasn't declared."""
    assert _CypherStore().supports("not-a-capability-2026") is False


# ---- ABC enforces required methods ----


def test_abc_rejects_partial_implementation() -> None:
    """Trying to instantiate a subclass missing required methods
    raises TypeError at construction (ABC behaviour)."""

    class _Incomplete(GraphStore):
        async def add_node(self, node: GraphNode) -> None: ...

        # Missing every other abstract method.

    with pytest.raises(TypeError, match="abstract"):
        _Incomplete()  # type: ignore[abstract]
