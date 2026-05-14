"""Live Postgres integration tests — gated on `RUN_LIVE_POSTGRES=1`.

CI does not run these. Local development:

    docker compose -f packages/agentforge-memory-postgres/docker-compose.dev.yml up -d
    RUN_LIVE_POSTGRES=1 \
      POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/agentforge \
      uv run pytest packages/agentforge-memory-postgres/tests/integration -v -m live

The fixtures pre- and post-clean both tables so tests don't leak
state between runs. Both the memory and vector conformance suites
are exercised against a real Postgres + pgvector instance.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from agentforge_core.testing import (
    run_hybrid_search_conformance,
    run_memory_conformance,
    run_vector_conformance,
)
from agentforge_memory_postgres import PostgresMemoryStore, PostgresVectorStore


def _live_enabled() -> bool:
    return os.environ.get("RUN_LIVE_POSTGRES") == "1"


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not _live_enabled(), reason="RUN_LIVE_POSTGRES not set"),
]


def _dsn() -> str:
    return os.environ.get(
        "POSTGRES_URL",
        "postgresql://postgres:postgres@localhost:5432/agentforge",
    )


@pytest.fixture
async def memory_store() -> AsyncIterator[PostgresMemoryStore]:
    store = await PostgresMemoryStore.from_dsn(_dsn())
    await store.init_schema()
    # Pre-clean: prior runs may have left rows around. Conformance
    # asserts an empty starting state for some checks, so wipe.
    await store._r.execute("TRUNCATE TABLE claims")
    try:
        yield store
    finally:
        await store._r.execute("TRUNCATE TABLE claims")
        await store.close()


@pytest.fixture
async def vector_store() -> AsyncIterator[PostgresVectorStore]:
    # Use a small dim so test fixtures don't have to construct large
    # vectors. The conformance suite asserts behaviour at any dim.
    store = await PostgresVectorStore.from_dsn(_dsn(), dimensions=8)
    await store.init_schema()
    await store._r.execute("TRUNCATE TABLE vectors")
    try:
        yield store
    finally:
        await store._r.execute("TRUNCATE TABLE vectors")
        await store.close()


@pytest.mark.asyncio
async def test_live_memory_conformance(memory_store: PostgresMemoryStore) -> None:
    await run_memory_conformance(memory_store)


@pytest.mark.asyncio
async def test_live_vector_conformance(vector_store: PostgresVectorStore) -> None:
    await run_vector_conformance(vector_store)


@pytest.mark.asyncio
async def test_live_hybrid_search_conformance(vector_store: PostgresVectorStore) -> None:
    """feat-022 follow-up: the live driver passes the opt-in
    hybrid-search conformance suite against real Postgres + the
    `embedding_tsv` generated column."""
    await run_hybrid_search_conformance(vector_store)


@pytest.mark.asyncio
async def test_live_migrations_apply_and_are_idempotent(
    memory_store: PostgresMemoryStore,
) -> None:
    """feat-024: the migration framework applies bundled migrations
    against a real Postgres + re-running is a no-op."""
    migrator = memory_store.migrator()
    # `init_schema()` already ran in the fixture, so applying again
    # should be a no-op.
    applied = await migrator.apply_pending()
    assert applied == []
    # And the status of every bundled migration is "applied" with a
    # matching checksum.
    statuses = await migrator.status()
    assert all(s.applied for s in statuses)
    assert all(s.checksum_match for s in statuses)
