"""Unit tests for `Neo4jGraphStore` against a fake Cypher runner.

We don't spin up Neo4j here — the fake runner (in `conftest.py`)
interprets the Cypher vocabulary the driver emits and routes to an
`InMemoryGraphStore` for correctness, recording every query for
inspection. Live tests against a real Neo4j live in
`tests/integration/`.
"""

from __future__ import annotations

import pytest
from agentforge_core.testing import run_graph_conformance
from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    GraphSegment,
)
from agentforge_memory_neo4j import Neo4jGraphStore

# Fixtures used: `graph_fake_runner` from `conftest.py`.


# ---- Round-trip ----


@pytest.mark.asyncio
async def test_add_and_get_node_round_trip(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    node = GraphNode(id="x", labels=("Doc",), properties={"k": 1})
    await store.add_node(node)
    fetched = await store.get_node("x")
    assert fetched == node


@pytest.mark.asyncio
async def test_get_node_unknown_returns_none(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    assert await store.get_node("ghost") is None


@pytest.mark.asyncio
async def test_add_edge_rejects_unknown_endpoint(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    await store.add_node(GraphNode(id="b"))
    with pytest.raises(ValueError, match="do not exist"):
        await store.add_edge(GraphEdge(src="ghost", dst="b", edge_type="X"))


# ---- Pattern match ----


@pytest.mark.asyncio
async def test_match_single_segment_compiles_correctly(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    await store.add_node(GraphNode(id="a", labels=("Doc",)))
    await store.add_node(GraphNode(id="b", labels=("Doc",)))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="CITES"))

    pattern = GraphPattern(
        segments=(GraphSegment(src_label="Doc", edge_type="CITES", dst_label="Doc"),)
    )
    paths = await store.match(pattern, limit=10)
    assert len(paths) == 1

    last_match_query = next(
        q for q in reversed(graph_fake_runner.queries) if q.cypher.startswith("MATCH (n0:AfNode)")
    )
    assert "$label_0" in last_match_query.cypher
    assert "$edge_type_0" in last_match_query.cypher
    assert last_match_query.params["label_0"] == "Doc"
    assert last_match_query.params["edge_type_0"] == "CITES"


@pytest.mark.asyncio
async def test_match_node_filter_emits_property_clause(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    await store.add_node(GraphNode(id="a", labels=("Doc",), properties={"topic": "ml"}))
    await store.add_node(GraphNode(id="b", labels=("Doc",), properties={"topic": "ml"}))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="CITES"))

    pattern = GraphPattern(
        segments=(GraphSegment(src_label="Doc", edge_type="CITES", dst_label="Doc"),),
        node_filters=({"topic": "ml"}, {}),
    )
    await store.match(pattern, limit=10)

    last_match_query = next(
        q for q in reversed(graph_fake_runner.queries) if q.cypher.startswith("MATCH (n0:AfNode)")
    )
    assert "n0.topic = $prop_0_topic" in last_match_query.cypher
    assert last_match_query.params["prop_0_topic"] == "ml"


@pytest.mark.asyncio
async def test_match_rejects_zero_limit(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    pattern = GraphPattern(segments=(GraphSegment(),))
    with pytest.raises(ValueError, match="limit"):
        await store.match(pattern, limit=0)


# ---- traverse ----


@pytest.mark.asyncio
async def test_traverse_interpolates_max_depth_literal(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    """Cypher requires a literal in *1..N — we interpolate `int(max_depth)`
    safely. The fake runner records the cypher, so we can assert on it."""
    store = Neo4jGraphStore(runner=graph_fake_runner)
    await store.add_node(GraphNode(id="a"))
    await store.traverse("a", max_depth=4)

    last_traverse = next(q for q in reversed(graph_fake_runner.queries) if "*1.." in q.cypher)
    assert "*1..4" in last_traverse.cypher


@pytest.mark.asyncio
async def test_traverse_rejects_zero_max_depth(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    with pytest.raises(ValueError, match="max_depth"):
        await store.traverse("a", max_depth=0)


@pytest.mark.asyncio
async def test_traverse_rejects_zero_limit(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    with pytest.raises(ValueError, match="limit"):
        await store.traverse("a", max_depth=2, limit=0)


@pytest.mark.asyncio
async def test_traverse_unknown_start_returns_empty(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    assert await store.traverse("ghost") == []


# ---- delete ----


@pytest.mark.asyncio
async def test_delete_node_unknown_returns_false(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    assert await store.delete_node("ghost") is False


@pytest.mark.asyncio
async def test_delete_node_with_edges_requires_cascade(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    await store.add_node(GraphNode(id="a"))
    await store.add_node(GraphNode(id="b"))
    await store.add_edge(GraphEdge(src="a", dst="b", edge_type="X"))
    with pytest.raises(ValueError, match="cascade"):
        await store.delete_node("a", cascade=False)


# ---- close ----


@pytest.mark.asyncio
async def test_close_closes_runner(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    await store.close()
    assert graph_fake_runner.closed is True


# ---- capabilities ----


def test_capabilities_declared(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    assert store.capabilities() == {"transactions", "cypher", "fulltext"}
    assert store.supports("cypher") is True
    assert store.supports("vector") is False


# ---- Schema bootstrap ----


@pytest.mark.asyncio
async def test_init_schema_emits_constraint_and_indexes(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jGraphStore(runner=graph_fake_runner)
    await store.init_schema()
    cyphers = [q.cypher for q in graph_fake_runner.queries]
    assert any("CREATE CONSTRAINT af_node_id" in c for c in cyphers)
    assert any("CREATE INDEX af_node_labels" in c for c in cyphers)
    assert any("CREATE INDEX af_edge_type" in c for c in cyphers)


# ---- Conformance ----


@pytest.mark.asyncio
async def test_passes_graph_conformance_suite(graph_fake_runner) -> None:  # type: ignore[no-untyped-def]
    """Driver must pass the same suite a live Neo4j is held to."""
    store = Neo4jGraphStore(runner=graph_fake_runner)
    await run_graph_conformance(store)
