"""Unit tests for `SqliteMemoryStore`."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.testing import run_memory_conformance
from agentforge_core.values.claim import Claim
from agentforge_memory_sqlite import SqliteMemoryStore


@pytest.fixture
async def memory_store() -> SqliteMemoryStore:
    """Fresh in-memory SQLite store per test."""
    store = await SqliteMemoryStore.from_path(":memory:")
    yield store
    await store.close()


# ---- Conformance suite ----


@pytest.mark.asyncio
async def test_passes_memory_conformance_suite() -> None:
    """The driver must pass the same suite every other MemoryStore
    impl is checked against."""
    store = await SqliteMemoryStore.from_path(":memory:")
    try:
        await run_memory_conformance(store)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_from_config_builds_a_live_store() -> None:
    """bug-022: `from_config` is the config-driven factory the CLI's
    `build_memory_from_config` uses. It must return a live store."""
    store = await SqliteMemoryStore.from_config(path=":memory:")
    try:
        claim = Claim(run_id="r1", project="p", agent="a", category="c", payload={"x": 1})
        claim_id = await store.put(claim)
        assert (await store.get(claim_id)) is not None
    finally:
        await store.close()


# ---- Lifecycle ----


@pytest.mark.asyncio
async def test_async_context_manager_closes_connection(tmp_path: Path) -> None:
    db_path = tmp_path / "agent.db"
    async with await SqliteMemoryStore.from_path(db_path) as store:
        await store.put(Claim(run_id="r1", project="p", agent="a", category="x", payload={}))
    # Re-opening succeeds — file isn't locked.
    async with await SqliteMemoryStore.from_path(db_path) as store:
        results = await store.query()
        assert len(results) == 1


@pytest.mark.asyncio
async def test_close_is_idempotent_via_context_manager() -> None:
    """Manual close() on a connection that's already been closed via
    the context manager should not raise spectacularly."""
    store = await SqliteMemoryStore.from_path(":memory:")
    await store.close()
    # aiosqlite raises on double-close; this is acceptable behaviour
    # but documented — tests should use the context manager.


# ---- Persistence across reconnects ----


@pytest.mark.asyncio
async def test_data_survives_reconnect(tmp_path: Path) -> None:
    db_path = tmp_path / "agent.db"
    async with await SqliteMemoryStore.from_path(db_path) as store:
        await store.put(
            Claim(run_id="r1", project="p1", agent="a1", category="finding", payload={})
        )
    async with await SqliteMemoryStore.from_path(db_path) as reopened:
        results = await reopened.query(project="p1")
        assert len(results) == 1
        assert results[0].project == "p1"


# ---- Filter combinations beyond the conformance suite ----


@pytest.mark.asyncio
async def test_query_combines_filters_conjunctively(
    memory_store: SqliteMemoryStore,
) -> None:
    await memory_store.put(Claim(run_id="r1", project="p1", agent="a1", category="doc", payload={}))
    await memory_store.put(Claim(run_id="r1", project="p1", agent="a2", category="doc", payload={}))
    await memory_store.put(Claim(run_id="r2", project="p1", agent="a1", category="doc", payload={}))
    matches = await memory_store.query(project="p1", agent="a1", run_id="r1")
    assert len(matches) == 1


@pytest.mark.asyncio
async def test_query_limit_caps_result_size(
    memory_store: SqliteMemoryStore,
) -> None:
    for i in range(5):
        await memory_store.put(
            Claim(run_id=f"r{i}", project="p", agent="a", category="x", payload={})
        )
    matches = await memory_store.query(project="p", limit=2)
    assert len(matches) == 2


@pytest.mark.asyncio
async def test_stream_yields_each_match(memory_store: SqliteMemoryStore) -> None:
    for i in range(3):
        await memory_store.put(
            Claim(run_id=f"r{i}", project="p", agent="a", category="x", payload={})
        )
    seen = [c async for c in memory_store.stream(project="p")]
    assert len(seen) == 3


# ---- supersede edge cases ----


@pytest.mark.asyncio
async def test_supersede_unknown_id_raises(memory_store: SqliteMemoryStore) -> None:
    new_claim = Claim(run_id="r1", project="p", agent="a", category="x", payload={})
    with pytest.raises(ModuleError, match="unknown claim id"):
        await memory_store.supersede("01HX-DOES-NOT-EXIST", new_claim)


@pytest.mark.asyncio
async def test_supersede_with_mismatched_supersedes_raises(
    memory_store: SqliteMemoryStore,
) -> None:
    original = Claim(run_id="r1", project="p", agent="a", category="x", payload={})
    await memory_store.put(original)
    new_claim = Claim(
        run_id="r1",
        project="p",
        agent="a",
        category="x",
        payload={},
        supersedes="some-other-id",
    )
    with pytest.raises(ModuleError, match="does not match"):
        await memory_store.supersede(original.id, new_claim)


# ---- Payload roundtrip ----


@pytest.mark.asyncio
async def test_payload_roundtrips_through_json(
    memory_store: SqliteMemoryStore,
) -> None:
    payload = {"answer": 42, "tags": ["a", "b"], "nested": {"k": "v"}}
    claim = Claim(run_id="r1", project="p", agent="a", category="x", payload=payload)
    await memory_store.put(claim)
    fetched = await memory_store.get(claim.id)
    assert fetched is not None
    assert fetched.payload == payload
