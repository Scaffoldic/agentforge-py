"""Unit tests for `SqliteVectorStore`."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
from agentforge_core.testing import run_vector_conformance
from agentforge_core.values.vector import VectorItem
from agentforge_memory_sqlite import SqliteVectorStore


@pytest.fixture
async def vector_store() -> SqliteVectorStore:
    store = await SqliteVectorStore.from_path(":memory:", dimensions=8)
    yield store
    await store.close()


# ---- Conformance suite ----


@pytest.mark.asyncio
async def test_passes_vector_conformance_suite() -> None:
    store = await SqliteVectorStore.from_path(":memory:", dimensions=8)
    try:
        await run_vector_conformance(store)
    finally:
        await store.close()


# ---- Constructor ----


def test_constructor_rejects_zero_dimensions() -> None:
    """The bare constructor doesn't connect; just rejects bad dim."""
    fake_conn = aiosqlite.connect(":memory:")  # not yet awaited
    with pytest.raises(ValueError, match="dimensions"):
        SqliteVectorStore(connection=fake_conn, dimensions=0)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_from_path_rejects_zero_dimensions(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="dimensions"):
        await SqliteVectorStore.from_path(tmp_path / "v.db", dimensions=0)


@pytest.mark.asyncio
async def test_from_path_rejects_dimension_change_on_reopen(
    tmp_path: Path,
) -> None:
    """Once a file is created with dimensions=N, re-opening with a
    different value must fail rather than silently corrupting."""
    db = tmp_path / "v.db"
    async with await SqliteVectorStore.from_path(db, dimensions=4):
        pass
    with pytest.raises(ValueError, match="dimensions"):
        await SqliteVectorStore.from_path(db, dimensions=8)


# ---- Persistence ----


@pytest.mark.asyncio
async def test_vectors_survive_reconnect(tmp_path: Path) -> None:
    db = tmp_path / "v.db"
    async with await SqliteVectorStore.from_path(db, dimensions=4) as store:
        await store.upsert(
            [
                VectorItem(id="a", vector=(1.0, 0.0, 0.0, 0.0), text="alpha"),
                VectorItem(id="b", vector=(0.0, 1.0, 0.0, 0.0), text="beta"),
            ]
        )
    async with await SqliteVectorStore.from_path(db, dimensions=4) as reopened:
        results = await reopened.search((1.0, 0.0, 0.0, 0.0), limit=2)
        ids = sorted(r.id for r in results)
        assert ids == ["a", "b"]
        assert results[0].id == "a"  # exact-match wins


# ---- Upsert + search basics ----


@pytest.mark.asyncio
async def test_upsert_replaces_existing_id(
    vector_store: SqliteVectorStore,
) -> None:
    v1 = VectorItem(id="x", vector=tuple([1.0] + [0.0] * 7), text="first")
    v2 = VectorItem(id="x", vector=tuple([0.0] * 7 + [1.0]), text="second")
    await vector_store.upsert([v1])
    await vector_store.upsert([v2])

    # Searching for the first vector now ranks the replacement low.
    results = await vector_store.search(tuple([1.0] + [0.0] * 7), limit=10)
    matching_x = [r for r in results if r.id == "x"]
    assert len(matching_x) == 1
    assert matching_x[0].text == "second"


@pytest.mark.asyncio
async def test_upsert_rejects_dimension_mismatch(
    vector_store: SqliteVectorStore,
) -> None:
    bad = VectorItem(id="bad", vector=(1.0, 0.0), text="x")
    with pytest.raises(ValueError, match="dimensions"):
        await vector_store.upsert([bad])


# ---- Metadata filter ----


@pytest.mark.asyncio
async def test_filter_metadata_keeps_only_matching_items(
    vector_store: SqliteVectorStore,
) -> None:
    await vector_store.upsert(
        [
            VectorItem(
                id="a",
                vector=tuple([1.0] + [0.0] * 7),
                text="a",
                metadata={"category": "doc"},
            ),
            VectorItem(
                id="b",
                vector=tuple([1.0] + [0.0] * 7),
                text="b",
                metadata={"category": "note"},
            ),
        ]
    )
    matches = await vector_store.search(
        tuple([1.0] + [0.0] * 7), limit=10, filter_metadata={"category": "doc"}
    )
    assert [m.id for m in matches] == ["a"]


@pytest.mark.asyncio
async def test_filter_metadata_complex_payload_roundtrips(
    vector_store: SqliteVectorStore,
) -> None:
    """Metadata is JSON-stored; nested dicts and lists must roundtrip."""
    await vector_store.upsert(
        [
            VectorItem(
                id="a",
                vector=tuple([1.0] + [0.0] * 7),
                text="a",
                metadata={"tags": ["x", "y"], "nested": {"k": 1}},
            ),
        ]
    )
    matches = await vector_store.search(tuple([1.0] + [0.0] * 7), limit=1)
    assert matches[0].metadata == {"tags": ["x", "y"], "nested": {"k": 1}}


# ---- Delete ----


@pytest.mark.asyncio
async def test_delete_returns_actual_removal_count(
    vector_store: SqliteVectorStore,
) -> None:
    await vector_store.upsert(
        [
            VectorItem(id="a", vector=tuple([1.0] + [0.0] * 7), text="a"),
            VectorItem(id="b", vector=tuple([0.0, 1.0] + [0.0] * 6), text="b"),
        ]
    )
    assert await vector_store.delete(["a", "b", "ghost"]) == 2
    assert await vector_store.delete(["a", "b"]) == 0
    assert await vector_store.delete([]) == 0


# ---- Defaults ----


def test_default_capabilities_empty() -> None:
    """Today's impl is brute-force; no native ANN, no hybrid search.
    A future v0.2 can declare `'native_ann'` after wiring sqlite-vec."""
    store = SqliteVectorStore.__new__(SqliteVectorStore)
    store._dim = 4  # type: ignore[attr-defined]
    assert store.capabilities() == set()
    assert store.supports("native_ann") is False
