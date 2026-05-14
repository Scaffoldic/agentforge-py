"""Unit tests for `InMemoryVectorStore` + the conformance suite."""

from __future__ import annotations

import itertools
import math

import pytest
from agentforge import InMemoryVectorStore
from agentforge_core.testing import (
    run_hybrid_search_conformance,
    run_vector_conformance,
)
from agentforge_core.values.vector import VectorItem


def _unit(*xs: float) -> tuple[float, ...]:
    """Return an L2-normalised vector. Inputs assumed nonzero."""
    norm = math.sqrt(sum(x * x for x in xs))
    return tuple(x / norm for x in xs)


# ---- Constructor ----


def test_constructor_rejects_zero_dimensions() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        InMemoryVectorStore(dimensions=0)


def test_constructor_rejects_negative_dimensions() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        InMemoryVectorStore(dimensions=-1)


def test_dimensions_returned_synchronously() -> None:
    store = InMemoryVectorStore(dimensions=128)
    assert store.dimensions() == 128


# ---- Upsert validation ----


@pytest.mark.asyncio
async def test_upsert_rejects_dimension_mismatch() -> None:
    store = InMemoryVectorStore(dimensions=3)
    bad = VectorItem(id="x", vector=(1.0, 0.0), text="x")
    with pytest.raises(ValueError, match="dimensions"):
        await store.upsert([bad])


@pytest.mark.asyncio
async def test_upsert_replaces_existing_id() -> None:
    """Re-upserting the same id is write-through — the old record is
    gone, no duplicates remain in the index."""
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert([VectorItem(id="x", vector=(1.0, 0.0), text="first")])
    await store.upsert([VectorItem(id="x", vector=(0.0, 1.0), text="second")])

    results = await store.search((1.0, 0.0), limit=10)
    ids = [r.id for r in results]
    assert ids.count("x") == 1
    assert results[0].text == "second"


# ---- Search ----


@pytest.mark.asyncio
async def test_search_returns_results_sorted_descending_by_score() -> None:
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert(
        [
            VectorItem(id="a", vector=_unit(1.0, 0.0), text="a"),  # score=1.0 vs (1,0)
            VectorItem(id="b", vector=_unit(0.5, 0.5), text="b"),  # ~0.707
            VectorItem(id="c", vector=_unit(0.0, 1.0), text="c"),  # 0.0 (orthogonal)
        ]
    )
    results = await store.search(_unit(1.0, 0.0), limit=3)
    assert [r.id for r in results] == ["a", "b", "c"]
    for prev, nxt in itertools.pairwise(results):
        assert prev.score >= nxt.score


@pytest.mark.asyncio
async def test_search_top_hit_for_identical_vector_scores_one() -> None:
    store = InMemoryVectorStore(dimensions=3)
    await store.upsert([VectorItem(id="x", vector=_unit(1.0, 1.0, 1.0), text="x")])
    results = await store.search(_unit(1.0, 1.0, 1.0), limit=1)
    assert results[0].id == "x"
    assert results[0].score == pytest.approx(1.0, abs=1e-6)


@pytest.mark.asyncio
async def test_search_orthogonal_scores_zero() -> None:
    """Orthogonal vectors clamp to 0.0 (per the contract)."""
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert([VectorItem(id="x", vector=(1.0, 0.0), text="x")])
    results = await store.search((0.0, 1.0), limit=1)
    assert results[0].score == pytest.approx(0.0, abs=1e-6)


@pytest.mark.asyncio
async def test_search_anti_correlated_clamps_to_zero() -> None:
    """A vector pointing the opposite direction has cosine -1; the
    contract clamps that to 0 so anti-correlation looks the same as
    'unrelated' (acceptable for text RAG)."""
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert([VectorItem(id="x", vector=(1.0, 0.0), text="x")])
    results = await store.search((-1.0, 0.0), limit=1)
    assert results[0].score == pytest.approx(0.0, abs=1e-6)


@pytest.mark.asyncio
async def test_search_respects_limit() -> None:
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert(
        [VectorItem(id=f"id-{i}", vector=_unit(1.0, float(i)), text="x") for i in range(5)]
    )
    assert len(await store.search((1.0, 0.0), limit=2)) == 2
    assert len(await store.search((1.0, 0.0), limit=10)) == 5


@pytest.mark.asyncio
async def test_search_rejects_zero_or_negative_limit() -> None:
    store = InMemoryVectorStore(dimensions=2)
    with pytest.raises(ValueError, match="limit"):
        await store.search((1.0, 0.0), limit=0)
    with pytest.raises(ValueError, match="limit"):
        await store.search((1.0, 0.0), limit=-1)


@pytest.mark.asyncio
async def test_search_rejects_dimension_mismatch_on_query() -> None:
    store = InMemoryVectorStore(dimensions=3)
    with pytest.raises(ValueError, match="dimensions"):
        await store.search((1.0, 0.0), limit=1)


# ---- Metadata filter ----


@pytest.mark.asyncio
async def test_filter_metadata_keeps_only_matching_items() -> None:
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert(
        [
            VectorItem(id="a", vector=(1.0, 0.0), text="a", metadata={"cat": "doc"}),
            VectorItem(id="b", vector=(1.0, 0.0), text="b", metadata={"cat": "note"}),
            VectorItem(id="c", vector=(1.0, 0.0), text="c", metadata={"cat": "doc"}),
        ]
    )
    results = await store.search((1.0, 0.0), limit=10, filter_metadata={"cat": "doc"})
    ids = sorted(r.id for r in results)
    assert ids == ["a", "c"]


@pytest.mark.asyncio
async def test_filter_metadata_requires_all_keys_to_match() -> None:
    """Multi-key filter is conjunctive (AND) — every (k, v) pair
    must match."""
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert(
        [
            VectorItem(
                id="a",
                vector=(1.0, 0.0),
                text="a",
                metadata={"cat": "doc", "year": 2024},
            ),
            VectorItem(
                id="b",
                vector=(1.0, 0.0),
                text="b",
                metadata={"cat": "doc", "year": 2023},
            ),
        ]
    )
    results = await store.search((1.0, 0.0), limit=10, filter_metadata={"cat": "doc", "year": 2024})
    assert [r.id for r in results] == ["a"]


@pytest.mark.asyncio
async def test_filter_metadata_empty_dict_is_no_op() -> None:
    """Empty filter_metadata dict matches everything — same as None."""
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert(
        [
            VectorItem(id="a", vector=(1.0, 0.0), text="a", metadata={"cat": "doc"}),
            VectorItem(id="b", vector=(1.0, 0.0), text="b", metadata={"cat": "note"}),
        ]
    )
    results = await store.search((1.0, 0.0), limit=10, filter_metadata={})
    assert len(results) == 2


# ---- Delete ----


@pytest.mark.asyncio
async def test_delete_returns_count_of_removed_items() -> None:
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert(
        [
            VectorItem(id="a", vector=(1.0, 0.0), text="a"),
            VectorItem(id="b", vector=(0.0, 1.0), text="b"),
        ]
    )
    assert await store.delete(["a", "b"]) == 2
    # Already empty — second delete returns 0.
    assert await store.delete(["a", "b"]) == 0


@pytest.mark.asyncio
async def test_delete_silently_drops_unknown_ids() -> None:
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert([VectorItem(id="real", vector=(1.0, 0.0), text="x")])
    # Mix known + unknown — only the known one counts.
    assert await store.delete(["real", "ghost"]) == 1


@pytest.mark.asyncio
async def test_delete_empty_list_returns_zero() -> None:
    store = InMemoryVectorStore(dimensions=2)
    assert await store.delete([]) == 0


# ---- close() ----


@pytest.mark.asyncio
async def test_close_clears_index() -> None:
    store = InMemoryVectorStore(dimensions=2)
    await store.upsert([VectorItem(id="x", vector=(1.0, 0.0), text="x")])
    await store.close()
    # After close, search returns nothing.
    results = await store.search((1.0, 0.0), limit=10)
    assert results == []


# ---- Capabilities (default) ----


def test_default_capabilities() -> None:
    """InMemoryVectorStore ships native hybrid search (feat-022)."""
    store = InMemoryVectorStore(dimensions=4)
    assert store.capabilities() == {"hybrid_search"}
    assert store.supports("native_ann") is False
    assert store.supports("hybrid_search") is True


# ---- Conformance suite ----


@pytest.mark.asyncio
async def test_passes_vector_conformance_suite() -> None:
    """The reference impl must pass the same suite every third-party
    driver will be checked against."""
    store = InMemoryVectorStore(dimensions=8)
    await run_vector_conformance(store)


@pytest.mark.asyncio
async def test_passes_hybrid_search_conformance_suite() -> None:
    """The reference impl declares `hybrid_search` and must pass the
    opt-in hybrid-search conformance suite (feat-022)."""
    store = InMemoryVectorStore(dimensions=8)
    await run_hybrid_search_conformance(store)


# ---- Auto-normalisation (calling code doesn't have to pre-normalise) ----


@pytest.mark.asyncio
async def test_unnormalised_vectors_still_score_correctly() -> None:
    """Callers can pass raw vectors without L2-normalising — the store
    normalises internally so cosine math is correct."""
    store = InMemoryVectorStore(dimensions=2)
    # Two parallel-but-different-magnitude vectors should still match.
    await store.upsert([VectorItem(id="x", vector=(3.0, 4.0), text="x")])
    results = await store.search((6.0, 8.0), limit=1)  # 2x the same direction
    assert results[0].score == pytest.approx(1.0, abs=1e-6)
