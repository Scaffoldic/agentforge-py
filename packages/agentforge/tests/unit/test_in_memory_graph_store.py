"""Unit tests for `InMemoryGraphStore` + the conformance suite."""

from __future__ import annotations

import pytest
from agentforge import InMemoryGraphStore
from agentforge_core.testing import run_graph_conformance
from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    GraphSegment,
)

# ---- Round-trip ----


@pytest.mark.asyncio
async def test_add_and_get_node_round_trip() -> None:
    store = InMemoryGraphStore()
    node = GraphNode(id="x", labels=("Doc",), properties={"k": 1})
    await store.add_node(node)
    fetched = await store.get_node("x")
    assert fetched == node


@pytest.mark.asyncio
async def test_get_node_unknown_returns_none() -> None:
    store = InMemoryGraphStore()
    assert await store.get_node("ghost") is None


@pytest.mark.asyncio
async def test_add_node_idempotent_replaces_properties() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="x", properties={"v": 1}))
    await store.add_node(GraphNode(id="x", properties={"v": 2}))
    fetched = await store.get_node("x")
    assert fetched is not None
    assert fetched.properties == {"v": 2}


# ---- Edge invariants ----


@pytest.mark.asyncio
async def test_add_edge_rejects_unknown_src() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="b"))
    with pytest.raises(ValueError, match="source"):
        await store.add_edge(GraphEdge(src="ghost", dst="b", edge_type="X"))


@pytest.mark.asyncio
async def test_add_edge_rejects_unknown_dst() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a"))
    with pytest.raises(ValueError, match="destination"):
        await store.add_edge(GraphEdge(src="a", dst="ghost", edge_type="X"))


@pytest.mark.asyncio
async def test_add_edge_idempotent_on_triple() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a"))
    await store.add_node(GraphNode(id="b"))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="X", properties={"w": 1}))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="X", properties={"w": 2}))
    edges = await store.get_edges("a")
    assert len(edges) == 1
    assert edges[0].properties == {"w": 2}


# ---- get_edges direction filter ----


@pytest.mark.asyncio
async def test_get_edges_directions() -> None:
    store = InMemoryGraphStore()
    for nid in ("a", "b", "c"):
        await store.add_node(GraphNode(id=nid))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="X"))
    await store.add_edge(GraphEdge(src="c", dst="a", edge_type="Y"))

    out_a = await store.get_edges("a", direction="out")
    assert [e.dst for e in out_a] == ["b"]

    in_a = await store.get_edges("a", direction="in")
    assert [e.src for e in in_a] == ["c"]

    any_a = await store.get_edges("a", direction="any")
    assert len(any_a) == 2


@pytest.mark.asyncio
async def test_get_edges_type_filter() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a"))
    await store.add_node(GraphNode(id="b"))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="X"))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="Y"))
    only_x = await store.get_edges("a", edge_type="X")
    assert [e.edge_type for e in only_x] == ["X"]


@pytest.mark.asyncio
async def test_get_edges_unknown_node_returns_empty() -> None:
    store = InMemoryGraphStore()
    assert await store.get_edges("ghost") == []


# ---- match() ----


@pytest.mark.asyncio
async def test_match_single_segment_returns_length_2_paths() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a", labels=("Doc",)))
    await store.add_node(GraphNode(id="b", labels=("Doc",)))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="CITES"))

    pattern = GraphPattern(
        segments=(GraphSegment(src_label="Doc", edge_type="CITES", dst_label="Doc"),)
    )
    paths = await store.match(pattern, limit=10)
    assert len(paths) == 1
    assert len(paths[0].nodes) == 2
    assert len(paths[0].edges) == 1


@pytest.mark.asyncio
async def test_match_respects_limit() -> None:
    store = InMemoryGraphStore()
    for nid in ("a", "b", "c"):
        await store.add_node(GraphNode(id=nid, labels=("X",)))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="E"))
    await store.add_edge(GraphEdge(src="a", dst="c", edge_type="E"))

    pattern = GraphPattern(segments=(GraphSegment(src_label="X", edge_type="E", dst_label="X"),))
    capped = await store.match(pattern, limit=1)
    assert len(capped) == 1


@pytest.mark.asyncio
async def test_match_node_filter_property_equality() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a", labels=("Doc",), properties={"topic": "ml"}))
    await store.add_node(GraphNode(id="b", labels=("Doc",), properties={"topic": "ml"}))
    await store.add_node(GraphNode(id="c", labels=("Doc",), properties={"topic": "bio"}))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="CITES"))
    await store.add_edge(GraphEdge(src="a", dst="c", edge_type="CITES"))

    pattern = GraphPattern(
        segments=(GraphSegment(src_label="Doc", edge_type="CITES", dst_label="Doc"),),
        node_filters=({}, {"topic": "ml"}),
    )
    paths = await store.match(pattern, limit=10)
    # Only a -> b should match (b has topic=ml; c has topic=bio)
    assert len(paths) == 1
    assert paths[0].nodes[1].id == "b"


@pytest.mark.asyncio
async def test_match_rejects_zero_limit() -> None:
    store = InMemoryGraphStore()
    pattern = GraphPattern(segments=(GraphSegment(),))
    with pytest.raises(ValueError, match="limit"):
        await store.match(pattern, limit=0)


# ---- traverse() ----


@pytest.mark.asyncio
async def test_traverse_max_depth_caps_path_length() -> None:
    store = InMemoryGraphStore()
    for nid in ("a", "b", "c", "d"):
        await store.add_node(GraphNode(id=nid))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="X"))
    await store.add_edge(GraphEdge(src="b", dst="c", edge_type="X"))
    await store.add_edge(GraphEdge(src="c", dst="d", edge_type="X"))

    paths_d2 = await store.traverse("a", max_depth=2)
    assert all(len(p.edges) <= 2 for p in paths_d2)
    # Should reach b (depth 1) and c (depth 2) but never d.
    reached = {p.nodes[-1].id for p in paths_d2}
    assert reached == {"b", "c"}


@pytest.mark.asyncio
async def test_traverse_edge_type_filter() -> None:
    store = InMemoryGraphStore()
    for nid in ("a", "b", "c"):
        await store.add_node(GraphNode(id=nid))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="ALLOWED"))
    await store.add_edge(GraphEdge(src="a", dst="c", edge_type="BLOCKED"))

    only_allowed = await store.traverse("a", edge_types=("ALLOWED",), max_depth=2)
    reached = {p.nodes[-1].id for p in only_allowed}
    assert reached == {"b"}


@pytest.mark.asyncio
async def test_traverse_unknown_start_returns_empty() -> None:
    store = InMemoryGraphStore()
    assert await store.traverse("ghost", max_depth=3) == []


@pytest.mark.asyncio
async def test_traverse_avoids_cycles() -> None:
    """A -> B -> A loop must terminate (no infinite recursion)."""
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a"))
    await store.add_node(GraphNode(id="b"))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="X"))
    await store.add_edge(GraphEdge(src="b", dst="a", edge_type="X"))

    paths = await store.traverse("a", max_depth=5)
    # Each path's nodes must be unique (no revisits)
    for p in paths:
        ids = [n.id for n in p.nodes]
        assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_traverse_rejects_zero_max_depth() -> None:
    store = InMemoryGraphStore()
    with pytest.raises(ValueError, match="max_depth"):
        await store.traverse("a", max_depth=0)


# ---- delete_node ----


@pytest.mark.asyncio
async def test_delete_node_unknown_returns_false() -> None:
    store = InMemoryGraphStore()
    assert await store.delete_node("ghost") is False


@pytest.mark.asyncio
async def test_delete_node_with_edges_requires_cascade() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a"))
    await store.add_node(GraphNode(id="b"))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="X"))
    with pytest.raises(ValueError, match="cascade"):
        await store.delete_node("a", cascade=False)


@pytest.mark.asyncio
async def test_delete_node_cascade_removes_incident_edges() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a"))
    await store.add_node(GraphNode(id="b"))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="X"))
    await store.add_edge(GraphEdge(src="b", dst="a", edge_type="Y"))
    assert await store.delete_node("a", cascade=True) is True
    # b's incident edges to a are gone
    assert (await store.get_edges("b", direction="any")) == []


# ---- delete_edge ----


@pytest.mark.asyncio
async def test_delete_edge_unknown_returns_false() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a"))
    await store.add_node(GraphNode(id="b"))
    assert await store.delete_edge("a", "b", edge_type="X") is False


@pytest.mark.asyncio
async def test_delete_edge_known_returns_true() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a"))
    await store.add_node(GraphNode(id="b"))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="X"))
    assert await store.delete_edge("a", "b", edge_type="X") is True
    assert (await store.get_edges("a")) == []


# ---- close ----


@pytest.mark.asyncio
async def test_close_clears_graph() -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="a"))
    await store.close()
    assert await store.get_node("a") is None


# ---- Capabilities ----


def test_default_capabilities_empty() -> None:
    store = InMemoryGraphStore()
    assert store.capabilities() == set()
    assert store.supports("cypher") is False


# ---- Conformance ----


@pytest.mark.asyncio
async def test_passes_graph_conformance_suite() -> None:
    """The reference impl must pass the same suite every third-party
    driver will be checked against."""
    store = InMemoryGraphStore()
    await run_graph_conformance(store)
