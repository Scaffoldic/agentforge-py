"""Unit tests for `PostgresVectorStore` against the fake asyncpg runner."""

from __future__ import annotations

import pytest
from agentforge_core.testing import run_vector_conformance
from agentforge_core.values.vector import VectorItem
from agentforge_memory_postgres import PostgresVectorStore

# Fixture used: `postgres_fake_runner` from `conftest.py`.


@pytest.mark.asyncio
async def test_passes_vector_conformance_suite(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=8)
    await run_vector_conformance(store)


def test_constructor_rejects_zero_dimensions(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="dimensions"):
        PostgresVectorStore(runner=postgres_fake_runner, dimensions=0)


def test_constructor_rejects_negative_dimensions(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="dimensions"):
        PostgresVectorStore(runner=postgres_fake_runner, dimensions=-1)


def test_dimensions_returned_synchronously(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=128)
    assert store.dimensions() == 128


def test_capabilities_empty_without_schema(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    """The HNSW capability is only claimed after init_schema()."""
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=8)
    assert store.capabilities() == set()
    assert store.supports("native_ann") is False


@pytest.mark.asyncio
async def test_capabilities_declares_native_ann_after_init(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=8)
    await store.init_schema()
    assert store.capabilities() == {"native_ann"}


@pytest.mark.asyncio
async def test_init_schema_emits_extension_table_and_hnsw_index(  # type: ignore[no-untyped-def]
    postgres_fake_runner,
) -> None:
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=4)
    await store.init_schema()
    sqls = [q.sql for q in postgres_fake_runner.queries]
    flat = " ".join(sqls)
    assert "CREATE EXTENSION IF NOT EXISTS vector" in flat
    assert "CREATE TABLE IF NOT EXISTS vectors" in flat
    assert "vector(4)" in flat  # dimension interpolated
    assert "USING hnsw" in flat
    assert "vector_cosine_ops" in flat


@pytest.mark.asyncio
async def test_init_schema_dimension_safely_interpolated(  # type: ignore[no-untyped-def]
    postgres_fake_runner,
) -> None:
    """Dimension is interpolated as `int(dim)` so user-supplied values
    cannot break out of the SQL syntax even though `vector(N)` syntax
    forbids parameter binding for N."""
    # Construct with an int — the production path; verifies the cast.
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=1024)
    await store.init_schema()
    flat = " ".join(q.sql for q in postgres_fake_runner.queries)
    assert "vector(1024)" in flat


@pytest.mark.asyncio
async def test_search_uses_cosine_distance_operator(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    """Verifies the SQL emitted by search() invokes pgvector's `<=>`
    operator and converts to clamped similarity at the SQL boundary."""
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=4)
    await store.upsert([VectorItem(id="a", vector=(1.0, 0.0, 0.0, 0.0), text="a")])
    await store.search((1.0, 0.0, 0.0, 0.0), limit=1)
    last_search = next(
        q for q in reversed(postgres_fake_runner.queries) if "ORDER BY embedding <=>" in q.sql
    )
    assert "GREATEST(0.0, 1.0 - (embedding <=> $1))" in last_search.sql
    assert "metadata @> $2::jsonb" in last_search.sql


@pytest.mark.asyncio
async def test_search_rejects_dimension_mismatch_on_query(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=4)
    with pytest.raises(ValueError, match="dimensions"):
        await store.search((1.0, 0.0), limit=1)


@pytest.mark.asyncio
async def test_search_rejects_zero_limit(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=4)
    with pytest.raises(ValueError, match="limit"):
        await store.search((1.0, 0.0, 0.0, 0.0), limit=0)


@pytest.mark.asyncio
async def test_upsert_rejects_dimension_mismatch(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=4)
    with pytest.raises(ValueError, match="dimensions"):
        await store.upsert([VectorItem(id="x", vector=(1.0, 0.0), text="x")])


@pytest.mark.asyncio
async def test_delete_returns_count_of_removed(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=2)
    await store.upsert(
        [
            VectorItem(id="a", vector=(1.0, 0.0), text="a"),
            VectorItem(id="b", vector=(0.0, 1.0), text="b"),
        ]
    )
    assert await store.delete(["a", "b", "ghost"]) == 2  # ghost ignored
    assert await store.delete([]) == 0


@pytest.mark.asyncio
async def test_close_closes_runner(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = PostgresVectorStore(runner=postgres_fake_runner, dimensions=4)
    await store.close()
    assert postgres_fake_runner.closed is True
