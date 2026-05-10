"""Live SurrealDB integration tests — gated on `RUN_LIVE_SURREAL=1`.

CI does not run these. Local development:

    docker compose -f packages/agentforge-memory-surrealdb/docker-compose.dev.yml up -d
    RUN_LIVE_SURREAL=1 SURREAL_URL=ws://localhost:8000/rpc \
      uv run pytest packages/agentforge-memory-surrealdb/tests/integration -v -m live
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from agentforge_core.testing import (
    run_graph_conformance,
    run_memory_conformance,
    run_vector_conformance,
)
from agentforge_memory_surrealdb import (
    SurrealGraphStore,
    SurrealMemoryStore,
    SurrealVectorStore,
)


def _live_enabled() -> bool:
    return os.environ.get("RUN_LIVE_SURREAL") == "1"


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not _live_enabled(), reason="RUN_LIVE_SURREAL not set"),
]


def _credentials() -> tuple[str, str, str, tuple[str, str] | None]:
    url = os.environ.get("SURREAL_URL", "ws://localhost:8000/rpc")
    namespace = os.environ.get("SURREAL_NAMESPACE", "agentforge_test")
    database = os.environ.get("SURREAL_DATABASE", "test")
    user = os.environ.get("SURREAL_USER", "root")
    password = os.environ.get("SURREAL_PASSWORD", "root")
    return url, namespace, database, (user, password)


@pytest.fixture
async def graph_store() -> AsyncIterator[SurrealGraphStore]:
    url, ns, db, auth = _credentials()
    store = await SurrealGraphStore.from_url(url, namespace=ns, database=db, auth=auth)
    await store.init_schema()
    await store._r.query("DELETE FROM af_edge; DELETE FROM af_node;")
    try:
        yield store
    finally:
        await store._r.query("DELETE FROM af_edge; DELETE FROM af_node;")
        await store.close()


@pytest.fixture
async def vector_store() -> AsyncIterator[SurrealVectorStore]:
    url, ns, db, auth = _credentials()
    store = await SurrealVectorStore.from_url(
        url, dimensions=8, namespace=ns, database=db, auth=auth
    )
    await store.init_schema()
    await store._r.query("DELETE FROM af_vector;")
    try:
        yield store
    finally:
        await store._r.query("DELETE FROM af_vector;")
        await store.close()


@pytest.fixture
async def memory_store() -> AsyncIterator[SurrealMemoryStore]:
    url, ns, db, auth = _credentials()
    store = await SurrealMemoryStore.from_url(url, namespace=ns, database=db, auth=auth)
    await store.init_schema()
    await store._r.query("DELETE FROM af_claim;")
    try:
        yield store
    finally:
        await store._r.query("DELETE FROM af_claim;")
        await store.close()


@pytest.mark.asyncio
async def test_live_graph_conformance(graph_store: SurrealGraphStore) -> None:
    await run_graph_conformance(graph_store)


@pytest.mark.asyncio
async def test_live_vector_conformance(vector_store: SurrealVectorStore) -> None:
    await run_vector_conformance(vector_store)


@pytest.mark.asyncio
async def test_live_memory_conformance(memory_store: SurrealMemoryStore) -> None:
    await run_memory_conformance(memory_store)
