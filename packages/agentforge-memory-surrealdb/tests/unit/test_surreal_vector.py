"""Unit tests for `SurrealVectorStore` against the fake runner."""

from __future__ import annotations

import pytest
from agentforge_core.testing import run_vector_conformance
from agentforge_memory_surrealdb import SurrealVectorStore


@pytest.mark.asyncio
async def test_passes_vector_conformance_suite(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealVectorStore(runner=surreal_fake_runner, dimensions=8)
    await run_vector_conformance(store)


def test_constructor_rejects_zero_dimensions(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="dimensions"):
        SurrealVectorStore(runner=surreal_fake_runner, dimensions=0)


def test_dimensions_returned_synchronously(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealVectorStore(runner=surreal_fake_runner, dimensions=64)
    assert store.dimensions() == 64


def test_capabilities_empty_without_schema(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    """The HNSW capability is only claimed after init_schema()."""
    store = SurrealVectorStore(runner=surreal_fake_runner, dimensions=8)
    assert store.capabilities() == set()


@pytest.mark.asyncio
async def test_capabilities_declares_native_ann_after_init(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealVectorStore(runner=surreal_fake_runner, dimensions=8)
    await store.init_schema()
    assert store.capabilities() == {"native_ann"}


@pytest.mark.asyncio
async def test_close_closes_runner(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = SurrealVectorStore(runner=surreal_fake_runner, dimensions=8)
    await store.close()
    assert surreal_fake_runner.closed is True
