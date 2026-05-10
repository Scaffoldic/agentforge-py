"""Unit tests for `Neo4jMemoryStore` against a fake Cypher runner."""

from __future__ import annotations

import pytest
from agentforge_core.testing import run_memory_conformance
from agentforge_core.values.claim import Claim
from agentforge_memory_neo4j import Neo4jMemoryStore

# Fixtures used: `memory_fake_runner` from `conftest.py`.


@pytest.mark.asyncio
async def test_passes_memory_conformance_suite(memory_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jMemoryStore(runner=memory_fake_runner)
    await run_memory_conformance(store)


@pytest.mark.asyncio
async def test_supersede_writes_graph_edge(memory_fake_runner) -> None:  # type: ignore[no-untyped-def]
    """The supersede chain must also be written as a graph edge so
    multi-hop graph traversals can reach prior versions."""
    store = Neo4jMemoryStore(runner=memory_fake_runner)
    old = Claim(run_id="r1", project="p", agent="a", category="finding", payload={"v": 1})
    await store.put(old)
    new = Claim(run_id="r1", project="p", agent="a", category="finding", payload={"v": 2})
    await store.supersede(old.id, new)
    assert (new.id, old.id) in memory_fake_runner.supersede_edges


@pytest.mark.asyncio
async def test_init_schema_emits_constraint_and_indexes(memory_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jMemoryStore(runner=memory_fake_runner)
    await store.init_schema()
    cyphers = [q.cypher for q in memory_fake_runner.queries]
    assert any("CREATE CONSTRAINT claim_id" in c for c in cyphers)
    assert any("CREATE INDEX claim_project_agent" in c for c in cyphers)


def test_capabilities_declared(memory_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jMemoryStore(runner=memory_fake_runner)
    assert store.capabilities() == {"transactions", "graph"}


@pytest.mark.asyncio
async def test_close_closes_runner(memory_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jMemoryStore(runner=memory_fake_runner)
    await store.close()
    assert memory_fake_runner.closed is True
