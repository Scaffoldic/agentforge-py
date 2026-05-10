"""Hypothesis property tests for `InMemoryGraphStore` invariants.

Verifies the locked GraphStore contract holds across arbitrarily-
shaped graphs:

  - `add_node` then `get_node` round-trips
  - re-adding a node replaces its properties (idempotent upsert)
  - `add_edge` is idempotent on `(src, dst, edge_type)`
  - traversal `max_depth` is honoured
  - `delete_node(cascade=True)` removes the node and incident edges
  - `Path` invariants are preserved for every result returned
"""

from __future__ import annotations

import itertools

import pytest
from agentforge import InMemoryGraphStore
from agentforge_core.values.graph import GraphEdge, GraphNode, Path
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Tame strategies — small graphs so each test runs fast.
_node_id = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=8)
_label = st.text(alphabet=st.characters(min_codepoint=65, max_codepoint=90), min_size=1, max_size=4)
_edge_type = st.sampled_from(["CITES", "AUTHORED_BY", "MENTIONS", "TAGGED"])


@settings(
    max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    nid=_node_id,
    labels=st.lists(_label, max_size=3, unique=True),
    props=st.dictionaries(st.text(min_size=1, max_size=4), st.integers(), max_size=3),
)
@pytest.mark.asyncio
async def test_add_get_node_round_trip(nid: str, labels: list[str], props: dict[str, int]) -> None:
    store = InMemoryGraphStore()
    node = GraphNode(id=nid, labels=tuple(labels), properties=props)
    await store.add_node(node)
    fetched = await store.get_node(nid)
    assert fetched == node


@settings(max_examples=50, deadline=None)
@given(
    nid=_node_id,
    props_a=st.dictionaries(st.text(min_size=1, max_size=3), st.integers(), max_size=2),
    props_b=st.dictionaries(st.text(min_size=1, max_size=3), st.integers(), max_size=2),
)
@pytest.mark.asyncio
async def test_add_node_idempotent_upsert_replaces_properties(
    nid: str, props_a: dict[str, int], props_b: dict[str, int]
) -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id=nid, properties=props_a))
    await store.add_node(GraphNode(id=nid, properties=props_b))
    fetched = await store.get_node(nid)
    assert fetched is not None
    assert fetched.properties == props_b


@settings(max_examples=30, deadline=None)
@given(
    src=_node_id,
    dst=_node_id,
    et=_edge_type,
    props_a=st.dictionaries(st.text(min_size=1, max_size=3), st.integers(), max_size=2),
    props_b=st.dictionaries(st.text(min_size=1, max_size=3), st.integers(), max_size=2),
)
@pytest.mark.asyncio
async def test_add_edge_idempotent_on_triple(
    src: str, dst: str, et: str, props_a: dict[str, int], props_b: dict[str, int]
) -> None:
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id=src))
    if dst != src:
        await store.add_node(GraphNode(id=dst))
    await store.add_edge(GraphEdge(src=src, dst=dst, edge_type=et, properties=props_a))
    await store.add_edge(GraphEdge(src=src, dst=dst, edge_type=et, properties=props_b))

    edges = await store.get_edges(src)
    matching = [e for e in edges if e.dst == dst and e.edge_type == et]
    assert len(matching) == 1
    assert matching[0].properties == props_b


@settings(max_examples=30, deadline=None)
@given(max_depth=st.integers(min_value=1, max_value=5))
@pytest.mark.asyncio
async def test_traverse_paths_obey_max_depth(max_depth: int) -> None:
    """Every path returned must have len(edges) <= max_depth."""
    store = InMemoryGraphStore()
    # Build a long chain a->b->c->d->e->f->g.
    chain = ["a", "b", "c", "d", "e", "f", "g"]
    for nid in chain:
        await store.add_node(GraphNode(id=nid))
    for s, d in itertools.pairwise(chain):
        await store.add_edge(GraphEdge(src=s, dst=d, edge_type="X"))

    paths = await store.traverse("a", max_depth=max_depth)
    for p in paths:
        assert len(p.edges) <= max_depth


@settings(max_examples=30, deadline=None)
@given(node_count=st.integers(min_value=2, max_value=10))
@pytest.mark.asyncio
async def test_cascade_delete_removes_incident_edges(node_count: int) -> None:
    """After `delete_node(cascade=True)`, no edge in the store
    references the deleted node."""
    store = InMemoryGraphStore()
    nodes = [f"n{i}" for i in range(node_count)]
    for nid in nodes:
        await store.add_node(GraphNode(id=nid))
    # Star-pattern: every node connects to n0.
    for nid in nodes[1:]:
        await store.add_edge(GraphEdge(src=nid, dst=nodes[0], edge_type="X"))

    deleted = await store.delete_node(nodes[0], cascade=True)
    assert deleted is True
    # No remaining edges reference n0.
    for nid in nodes[1:]:
        out = await store.get_edges(nid, direction="any")
        for e in out:
            assert e.src != nodes[0]
            assert e.dst != nodes[0]


@settings(max_examples=30, deadline=None)
@given(
    n_nodes=st.integers(min_value=2, max_value=6),
    seed=st.integers(),
)
@pytest.mark.asyncio
async def test_path_invariants_hold_for_traversal_results(n_nodes: int, seed: int) -> None:
    """Every Path returned by traverse() satisfies len(edges) == len(nodes) - 1
    (Path's model_validator enforces this — but the property test confirms
    drivers populate paths correctly under arbitrary graphs)."""
    store = InMemoryGraphStore()
    nodes = [f"n{i}" for i in range(n_nodes)]
    for nid in nodes:
        await store.add_node(GraphNode(id=nid))
    # Deterministic edge layout from seed.
    for i in range(n_nodes - 1):
        if (seed >> i) & 1:
            await store.add_edge(GraphEdge(src=nodes[i], dst=nodes[i + 1], edge_type="X"))
    paths = await store.traverse("n0", max_depth=n_nodes)
    for p in paths:
        # Pydantic enforces this on construction; this assertion is
        # defence-in-depth that the driver respects the contract.
        assert isinstance(p, Path)
        assert len(p.edges) == len(p.nodes) - 1
