"""Unit tests for `PostgresMemoryStore` against a fake asyncpg runner."""

from __future__ import annotations

import pytest
from agentforge_core.testing import run_memory_conformance
from agentforge_core.values.claim import Claim
from agentforge_memory_postgres import PostgresMemoryStore

# Fixture used: `postgres_fake_runner` from `conftest.py`.


@pytest.mark.asyncio
async def test_passes_memory_conformance_suite(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresMemoryStore(runner=postgres_fake_runner)
    await run_memory_conformance(store)


@pytest.mark.asyncio
async def test_init_schema_emits_create_table_and_indexes(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresMemoryStore(runner=postgres_fake_runner)
    await store.init_schema()
    sqls = [q.sql for q in postgres_fake_runner.queries]
    assert any("CREATE TABLE IF NOT EXISTS claims" in s for s in sqls)
    assert any("idx_claims_project_agent" in s for s in sqls)
    assert any("idx_claims_run_id" in s for s in sqls)
    assert any("idx_claims_category" in s for s in sqls)


def test_capabilities_declared(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresMemoryStore(runner=postgres_fake_runner)
    assert store.capabilities() == {"transactions"}
    assert store.supports("transactions") is True
    assert store.supports("native_ann") is False


@pytest.mark.asyncio
async def test_close_closes_runner(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresMemoryStore(runner=postgres_fake_runner)
    await store.close()
    assert postgres_fake_runner.closed is True


@pytest.mark.asyncio
async def test_upsert_uses_dollar_param_placeholders(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    """asyncpg's wire protocol uses `$1, $2, …` (numbered) — the
    driver must emit those, not aiosqlite's `?` placeholders."""
    store = PostgresMemoryStore(runner=postgres_fake_runner)
    await store.put(
        Claim(run_id="r1", project="p", agent="a", category="finding", payload={"v": 1})
    )
    last_query = postgres_fake_runner.queries[-1].sql
    assert "$1" in last_query
    assert "$2" in last_query
    assert "?" not in last_query


@pytest.mark.asyncio
async def test_query_filter_emits_dollar_placeholders_in_order(  # type: ignore[no-untyped-def]
    postgres_fake_runner,
) -> None:
    """Filter columns map to `$1, $2, …` in their conjunctive order;
    LIMIT picks up the next index. Verifies the offset arithmetic in
    `_build_filter_sql`."""
    store = PostgresMemoryStore(runner=postgres_fake_runner)
    await store.put(Claim(run_id="r1", project="p1", agent="a1", category="finding", payload={}))
    await store.query(project="p1", agent="a1", limit=5)
    last_query = postgres_fake_runner.queries[-1].sql
    assert "project = $1" in last_query
    assert "agent = $2" in last_query
    assert "LIMIT $3" in last_query
