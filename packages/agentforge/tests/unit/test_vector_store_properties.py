"""Property tests for `InMemoryVectorStore` invariants.

These tests use Hypothesis to fuzz the locked behaviours that every
`VectorStore` driver must respect — but exercise them on the
in-memory reference impl so they run in CI without external services.
The same suite (run_vector_conformance) is what third-party drivers
must pass, so these properties hold across the contract.
"""

from __future__ import annotations

import itertools
import math

import pytest
from agentforge import InMemoryVectorStore
from agentforge_core.values.vector import VectorItem
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# A modest dimensionality keeps the fuzzer fast while still exercising
# real cosine math (more than two components).
_DIM = 4


def _floats(*, n: int) -> st.SearchStrategy[tuple[float, ...]]:
    """Build n-component vectors, biased to non-trivial directions."""
    return st.lists(
        st.floats(
            min_value=-10.0,
            max_value=10.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=n,
        max_size=n,
    ).map(tuple)


def _nonzero_floats(*, n: int) -> st.SearchStrategy[tuple[float, ...]]:
    """Vectors guaranteed to have nonzero L2 norm (avoid div-by-zero
    on the 'all components are 0' edge case)."""
    return _floats(n=n).filter(lambda v: math.sqrt(sum(x * x for x in v)) > 1e-3)


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(vector=_nonzero_floats(n=_DIM))
@pytest.mark.asyncio
async def test_self_search_is_top_hit_with_score_one(
    vector: tuple[float, ...],
) -> None:
    """Searching with a vector identical to an upserted one always
    returns that item first with score ~= 1.0 (after L2 normalisation)."""
    store = InMemoryVectorStore(dimensions=_DIM)
    await store.upsert([VectorItem(id="x", vector=vector, text="x")])
    results = await store.search(vector, limit=1)
    assert len(results) == 1
    assert results[0].id == "x"
    assert results[0].score == pytest.approx(1.0, abs=1e-6)


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(vector=_nonzero_floats(n=_DIM), scale=st.floats(min_value=0.1, max_value=100.0))
@pytest.mark.asyncio
async def test_score_is_invariant_to_query_magnitude(
    vector: tuple[float, ...],
    scale: float,
) -> None:
    """Cosine similarity is direction-only; scaling the query vector
    doesn't change ranking. The store normalises internally."""
    store = InMemoryVectorStore(dimensions=_DIM)
    await store.upsert([VectorItem(id="x", vector=vector, text="x")])
    plain = await store.search(vector, limit=1)
    scaled = await store.search(tuple(c * scale for c in vector), limit=1)
    assert plain[0].score == pytest.approx(scaled[0].score, abs=1e-6)


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(vector=_nonzero_floats(n=_DIM), scale=st.floats(min_value=0.1, max_value=100.0))
@pytest.mark.asyncio
async def test_score_is_invariant_to_indexed_magnitude(
    vector: tuple[float, ...],
    scale: float,
) -> None:
    """Same property the other direction — scaling an upserted vector
    doesn't change its rank vs. the unchanged query."""
    store_plain = InMemoryVectorStore(dimensions=_DIM)
    store_scaled = InMemoryVectorStore(dimensions=_DIM)
    await store_plain.upsert([VectorItem(id="x", vector=vector, text="x")])
    await store_scaled.upsert(
        [VectorItem(id="x", vector=tuple(c * scale for c in vector), text="x")]
    )
    plain = await store_plain.search(vector, limit=1)
    scaled = await store_scaled.search(vector, limit=1)
    assert plain[0].score == pytest.approx(scaled[0].score, abs=1e-6)


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    n_items=st.integers(min_value=2, max_value=8),
    query=_nonzero_floats(n=_DIM),
)
@pytest.mark.asyncio
async def test_search_results_are_sorted_descending_by_score(
    n_items: int,
    query: tuple[float, ...],
) -> None:
    """For any non-empty store, search() returns items ordered by
    score descending. Property holds regardless of insertion order."""
    store = InMemoryVectorStore(dimensions=_DIM)
    items = [
        VectorItem(
            id=f"id-{i}",
            vector=(float(i + 1), float((i + 2) % 3), float((i + 1) % 5), 1.0),
            text=f"text {i}",
        )
        for i in range(n_items)
    ]
    await store.upsert(items)
    results = await store.search(query, limit=n_items)
    for prev, nxt in itertools.pairwise(results):
        assert prev.score >= nxt.score


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    n_items=st.integers(min_value=1, max_value=5),
    requested_limit=st.integers(min_value=1, max_value=20),
    query=_nonzero_floats(n=_DIM),
)
@pytest.mark.asyncio
async def test_search_returns_at_most_limit_results(
    n_items: int,
    requested_limit: int,
    query: tuple[float, ...],
) -> None:
    """Result count is bounded by both `limit` and the actual store
    size — never returns more than min(N, limit) items."""
    store = InMemoryVectorStore(dimensions=_DIM)
    items = [
        VectorItem(id=f"id-{i}", vector=(1.0, float(i), 0.5, 0.0), text=f"t{i}")
        for i in range(n_items)
    ]
    await store.upsert(items)
    results = await store.search(query, limit=requested_limit)
    assert len(results) <= min(requested_limit, n_items)


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    bad_dim=st.integers(min_value=1, max_value=10).filter(lambda d: d != _DIM),
)
@pytest.mark.asyncio
async def test_dimension_mismatch_always_raises(bad_dim: int) -> None:
    """Any vector whose length differs from dimensions() must raise
    ValueError on upsert AND on search. This is the contract — the
    store never silently truncates or pads."""
    store = InMemoryVectorStore(dimensions=_DIM)
    bad_vector = tuple([0.5] * bad_dim)
    with pytest.raises(ValueError, match="dimensions"):
        await store.upsert([VectorItem(id="x", vector=bad_vector, text="x")])
    with pytest.raises(ValueError, match="dimensions"):
        await store.search(bad_vector, limit=1)


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    n_items=st.integers(min_value=1, max_value=10),
)
@pytest.mark.asyncio
async def test_delete_returns_count_of_removed_items(n_items: int) -> None:
    """Round-trip property: upserting N items and deleting all their
    ids must report exactly N removals."""
    store = InMemoryVectorStore(dimensions=_DIM)
    items = [
        VectorItem(id=f"id-{i}", vector=(1.0, float(i), 0.0, 0.0), text=f"t{i}")
        for i in range(n_items)
    ]
    await store.upsert(items)
    removed = await store.delete([item.id for item in items])
    assert removed == n_items
    # And re-deleting the same ids reports 0 — they're already gone.
    assert await store.delete([item.id for item in items]) == 0
