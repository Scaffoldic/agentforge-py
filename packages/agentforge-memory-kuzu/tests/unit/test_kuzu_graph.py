"""Unit + conformance tests for `KuzuGraphStore` (feat-027).

The headline is the cross-driver conformance suite run against a **real
embedded database in a temp dir** — no server, no credentials, fully
offline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge_core.testing import run_graph_conformance
from agentforge_core.values.graph import GraphEdge, GraphNode, GraphPattern, GraphSegment
from agentforge_memory_kuzu import KuzuGraphStore


@pytest.fixture
async def store(tmp_path: Path):
    s = await KuzuGraphStore.from_path(tmp_path / "graph.ckg")
    try:
        yield s
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_graph_conformance(tmp_path: Path) -> None:
    async with await KuzuGraphStore.from_path(tmp_path / "conf.ckg") as s:
        await run_graph_conformance(s)


@pytest.mark.asyncio
async def test_from_path_persists_across_reopen(tmp_path: Path) -> None:
    path = tmp_path / "persist.ckg"
    store = await KuzuGraphStore.from_path(path)
    await store.add_node(GraphNode(id="a", labels=("Doc",), properties={"topic": "ml"}))
    await store.close()

    reopened = await KuzuGraphStore.from_path(path)
    try:
        node = await reopened.get_node("a")
        assert node is not None
        assert node.labels == ("Doc",)
        assert node.properties == {"topic": "ml"}
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_from_config_equivalent_to_from_path(tmp_path: Path) -> None:
    store = await KuzuGraphStore.from_config(path=tmp_path / "cfg.ckg")
    try:
        await store.add_node(GraphNode(id="x"))
        assert (await store.get_node("x")) is not None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_add_node_is_idempotent_upsert(store: KuzuGraphStore) -> None:
    await store.add_node(GraphNode(id="a", properties={"v": 1}))
    await store.add_node(GraphNode(id="a", properties={"v": 2, "w": 3}))
    node = await store.get_node("a")
    assert node is not None
    assert node.properties == {"v": 2, "w": 3}


@pytest.mark.asyncio
async def test_add_edge_unknown_endpoint_raises(store: KuzuGraphStore) -> None:
    await store.add_node(GraphNode(id="a"))
    with pytest.raises(ValueError, match="do not exist"):
        await store.add_edge(GraphEdge(src="ghost", dst="a", edge_type="CITES"))


@pytest.mark.asyncio
async def test_get_edges_direction_and_filter(store: KuzuGraphStore) -> None:
    for nid in ("a", "b", "c"):
        await store.add_node(GraphNode(id=nid))
    await store.add_edge(GraphEdge(src="b", dst="a", edge_type="CITES"))
    await store.add_edge(GraphEdge(src="c", dst="a", edge_type="AUTHORED"))

    out_b = await store.get_edges("b", direction="out")
    assert [(e.src, e.dst, e.edge_type) for e in out_b] == [("b", "a", "CITES")]

    in_a = await store.get_edges("a", direction="in")
    assert {(e.src, e.edge_type) for e in in_a} == {("b", "CITES"), ("c", "AUTHORED")}

    in_a_cites = await store.get_edges("a", direction="in", edge_type="CITES")
    assert {e.src for e in in_a_cites} == {"b"}

    any_a = await store.get_edges("a", direction="any")
    assert len(any_a) == 2  # 0 out + 2 in
    assert await store.get_edges("missing") == []


@pytest.mark.asyncio
async def test_edge_upsert_replaces_properties(store: KuzuGraphStore) -> None:
    await store.add_node(GraphNode(id="a"))
    await store.add_node(GraphNode(id="b"))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="CITES", properties={"w": 1}))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="CITES", properties={"w": 9}))
    edges = await store.get_edges("a", direction="out")
    assert len(edges) == 1
    assert edges[0].properties == {"w": 9}


@pytest.mark.asyncio
async def test_traverse_depth_and_cycle_safety(store: KuzuGraphStore) -> None:
    for nid in ("a", "b", "c"):
        await store.add_node(GraphNode(id=nid, properties={"text": nid}))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="CITES"))
    await store.add_edge(GraphEdge(src="b", dst="c", edge_type="CITES"))
    await store.add_edge(GraphEdge(src="c", dst="a", edge_type="CITES"))  # cycle

    paths = await store.traverse("a", max_depth=2)
    # every path bounded by depth; no path revisits the seed.
    assert all(len(p.edges) <= 2 for p in paths)
    assert any(p.nodes[-1].id == "c" for p in paths)  # a→b→c reached
    # edge-type filter excludes a foreign type
    await store.add_node(GraphNode(id="d"))
    await store.add_edge(GraphEdge(src="a", dst="d", edge_type="OTHER"))
    cites_only = await store.traverse("a", edge_types=("CITES",), max_depth=1)
    assert {p.nodes[-1].id for p in cites_only} == {"b"}
    assert await store.traverse("ghost", max_depth=2) == []


@pytest.mark.asyncio
async def test_traverse_rejects_bad_bounds(store: KuzuGraphStore) -> None:
    await store.add_node(GraphNode(id="a"))
    with pytest.raises(ValueError, match="max_depth"):
        await store.traverse("a", max_depth=0)
    with pytest.raises(ValueError, match="limit"):
        await store.traverse("a", limit=0)


@pytest.mark.asyncio
async def test_match_pattern(store: KuzuGraphStore) -> None:
    await store.add_node(GraphNode(id="a", labels=("Doc",)))
    await store.add_node(GraphNode(id="b", labels=("Doc",)))
    await store.add_node(GraphNode(id="c", labels=("Author",)))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="CITES"))
    await store.add_edge(GraphEdge(src="a", dst="c", edge_type="AUTHORED"))

    pattern = GraphPattern(
        segments=(GraphSegment(src_label="Doc", edge_type="CITES", dst_label="Doc"),)
    )
    paths = await store.match(pattern, limit=10)
    assert len(paths) == 1
    assert len(paths[0].nodes) == 2
    assert paths[0].edges[0].edge_type == "CITES"
    assert (await store.match(pattern, limit=1)).__len__() <= 1
    with pytest.raises(ValueError, match="limit"):
        await store.match(pattern, limit=0)


@pytest.mark.asyncio
async def test_delete_node_and_edge(store: KuzuGraphStore) -> None:
    await store.add_node(GraphNode(id="a"))
    await store.add_node(GraphNode(id="b"))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="CITES"))

    assert await store.delete_node("nope") is False
    with pytest.raises(ValueError, match="incident edge"):
        await store.delete_node("a", cascade=False)
    assert await store.delete_node("a", cascade=True) is True
    assert await store.get_node("a") is None
    assert await store.get_edges("b", direction="in") == []
    assert await store.delete_edge("b", "x", edge_type="CITES") is False


def test_capabilities() -> None:
    # Pure value check — capabilities() is sync and store-independent.
    caps = KuzuGraphStore(database=None, connection=None).capabilities()
    assert caps == {"cypher"}
