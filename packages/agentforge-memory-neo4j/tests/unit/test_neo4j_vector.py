"""Unit tests for `Neo4jVectorStore` (feat-025)."""

from __future__ import annotations

import pytest
from agentforge_core.testing import (
    run_hybrid_search_conformance,
    run_vector_conformance,
)
from agentforge_memory_neo4j import Neo4jVectorStore


def test_constructor_rejects_zero_dimensions(vector_fake_runner) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="dimensions"):
        Neo4jVectorStore(runner=vector_fake_runner, dimensions=0)


def test_constructor_rejects_negative_dimensions(vector_fake_runner) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="dimensions"):
        Neo4jVectorStore(runner=vector_fake_runner, dimensions=-1)


def test_capabilities_empty_without_schema(vector_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jVectorStore(runner=vector_fake_runner, dimensions=8)
    assert store.capabilities() == set()
    assert store.supports("native_ann") is False
    assert store.supports("hybrid_search") is False


@pytest.mark.asyncio
async def test_capabilities_declared_after_init_schema(vector_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jVectorStore(runner=vector_fake_runner, dimensions=8)
    await store.init_schema()
    assert store.capabilities() == {"native_ann", "hybrid_search"}


@pytest.mark.asyncio
async def test_passes_vector_conformance_suite(vector_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jVectorStore(runner=vector_fake_runner, dimensions=8, ann_indexed=True)
    await run_vector_conformance(store)


@pytest.mark.asyncio
async def test_passes_hybrid_search_conformance_suite(vector_fake_runner) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jVectorStore(runner=vector_fake_runner, dimensions=8)
    await store.init_schema()
    await run_hybrid_search_conformance(store)


@pytest.mark.asyncio
async def test_init_schema_emits_vector_and_fulltext_index_creation(
    vector_fake_runner,
) -> None:  # type: ignore[no-untyped-def]
    store = Neo4jVectorStore(runner=vector_fake_runner, dimensions=768)
    await store.init_schema()
    cyphers = " ".join(q.cypher for q in vector_fake_runner.queries)
    assert "CREATE VECTOR INDEX af_vector_embedding" in cyphers
    assert "CREATE FULLTEXT INDEX af_vector_text" in cyphers
    assert "CREATE CONSTRAINT af_vector_id" in cyphers
    # Dimension substitution from feat-024 v0.3 template helper.
    assert "768" in cyphers
    assert "${dimensions}" not in cyphers
