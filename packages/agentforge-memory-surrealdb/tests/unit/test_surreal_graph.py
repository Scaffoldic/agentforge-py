"""Unit tests for `SurrealGraphStore` against the fake runner."""

from __future__ import annotations

import pytest
from agentforge_core.testing import run_graph_conformance
from agentforge_core.values.graph import GraphEdge, GraphNode
from agentforge_memory_surrealdb import SurrealGraphStore


@pytest.mark.asyncio
async def test_passes_graph_conformance_suite(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealGraphStore(runner=surreal_fake_runner)
    await run_graph_conformance(store)


@pytest.mark.asyncio
async def test_add_edge_rejects_unknown_endpoint(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealGraphStore(runner=surreal_fake_runner)
    await store.add_node(GraphNode(id="b"))
    with pytest.raises(ValueError, match="do not exist"):
        await store.add_edge(GraphEdge(src="ghost", dst="b", edge_type="X"))


@pytest.mark.asyncio
async def test_init_schema_emits_define_statements(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealGraphStore(runner=surreal_fake_runner)
    await store.init_schema()
    sqls = [q.surrealql for q in surreal_fake_runner.queries]
    assert any("DEFINE TABLE IF NOT EXISTS af_node" in s for s in sqls)
    assert any("DEFINE TABLE IF NOT EXISTS af_edge" in s for s in sqls)


def test_capabilities_declared(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealGraphStore(runner=surreal_fake_runner)
    assert store.capabilities() == {"transactions", "surrealql", "vector", "live_query"}


@pytest.mark.asyncio
async def test_close_closes_runner(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealGraphStore(runner=surreal_fake_runner)
    await store.close()
    assert surreal_fake_runner.closed is True
