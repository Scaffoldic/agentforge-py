"""Unit tests for `SurrealMemoryStore` against the fake runner."""

from __future__ import annotations

import pytest
from agentforge_core.testing import run_memory_conformance
from agentforge_memory_surrealdb import SurrealMemoryStore


@pytest.mark.asyncio
async def test_passes_memory_conformance_suite(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealMemoryStore(runner=surreal_fake_runner)
    await run_memory_conformance(store)


@pytest.mark.asyncio
async def test_init_schema_emits_define_statements(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealMemoryStore(runner=surreal_fake_runner)
    await store.init_schema()
    sqls = [q.surrealql for q in surreal_fake_runner.queries]
    assert any("DEFINE TABLE IF NOT EXISTS af_claim" in s for s in sqls)


def test_capabilities_declared(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealMemoryStore(runner=surreal_fake_runner)
    assert store.capabilities() == {"transactions"}


@pytest.mark.asyncio
async def test_close_closes_runner(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealMemoryStore(runner=surreal_fake_runner)
    await store.close()
    assert surreal_fake_runner.closed is True
