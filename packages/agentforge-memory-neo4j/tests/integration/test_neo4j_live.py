"""Live Neo4j integration tests — gated on `RUN_LIVE_NEO4J=1`.

CI does not run these. Local development:

    docker compose -f packages/agentforge-memory-neo4j/docker-compose.dev.yml up -d
    RUN_LIVE_NEO4J=1 NEO4J_URL=bolt://localhost:7687 \
      NEO4J_USER=neo4j NEO4J_PASSWORD=test \
      uv run pytest packages/agentforge-memory-neo4j/tests/integration -v -m live
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from agentforge_core.testing import run_graph_conformance, run_memory_conformance
from agentforge_memory_neo4j import Neo4jGraphStore, Neo4jMemoryStore


def _live_enabled() -> bool:
    return os.environ.get("RUN_LIVE_NEO4J") == "1"


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not _live_enabled(), reason="RUN_LIVE_NEO4J not set"),
]


def _credentials() -> tuple[str, tuple[str, str], str]:
    url = os.environ.get("NEO4J_URL", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "test")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    return url, (user, password), database


@pytest.fixture
async def graph_store() -> AsyncIterator[Neo4jGraphStore]:
    url, auth, database = _credentials()
    store = await Neo4jGraphStore.from_url(url, auth=auth, database=database)
    await store.init_schema()
    # Wipe the graph DB before each test (only the AfNode subgraph).
    await store._r.execute_write("MATCH (n:AfNode) DETACH DELETE n", {})
    try:
        yield store
    finally:
        await store._r.execute_write("MATCH (n:AfNode) DETACH DELETE n", {})
        await store.close()


@pytest.fixture
async def memory_store() -> AsyncIterator[Neo4jMemoryStore]:
    url, auth, database = _credentials()
    store = await Neo4jMemoryStore.from_url(url, auth=auth, database=database)
    await store.init_schema()
    await store._r.execute_write("MATCH (c:Claim) DETACH DELETE c", {})
    try:
        yield store
    finally:
        await store._r.execute_write("MATCH (c:Claim) DETACH DELETE c", {})
        await store.close()


@pytest.mark.asyncio
async def test_live_graph_conformance(graph_store: Neo4jGraphStore) -> None:
    await run_graph_conformance(graph_store)


@pytest.mark.asyncio
async def test_live_memory_conformance(memory_store: Neo4jMemoryStore) -> None:
    await run_memory_conformance(memory_store)
