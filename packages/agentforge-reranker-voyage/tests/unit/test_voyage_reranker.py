"""Unit tests for `VoyageReranker` (feat-021 vendor follow-up)."""

from __future__ import annotations

import pytest
from agentforge_core.testing import run_reranker_conformance
from agentforge_core.values.vector import VectorMatch
from agentforge_reranker_voyage import VoyageReranker
from agentforge_reranker_voyage._inmem_runner import FakeVoyageRunner


def _candidates() -> list[VectorMatch]:
    return [
        VectorMatch(id="a", text="alpha", score=0.5, metadata={"i": 0}),
        VectorMatch(id="b", text="beta", score=0.5, metadata={"i": 1}),
        VectorMatch(id="c", text="gamma", score=0.5, metadata={"i": 2}),
    ]


@pytest.mark.asyncio
async def test_rerank_sorts_per_api_response_order() -> None:
    runner = FakeVoyageRunner(results=[(2, 0.95), (0, 0.7), (1, 0.2)])
    reranker = VoyageReranker(runner=runner, model="rerank-2")
    results = await reranker.rerank("q", _candidates())
    assert [r.id for r in results] == ["c", "a", "b"]
    assert results[0].score == 0.95


@pytest.mark.asyncio
async def test_rerank_clamps_out_of_range_scores() -> None:
    runner = FakeVoyageRunner(results=[(0, 1.5), (1, -0.2), (2, 0.5)])
    reranker = VoyageReranker(runner=runner)
    results = await reranker.rerank("q", _candidates())
    assert all(0.0 <= r.score <= 1.0 for r in results)


@pytest.mark.asyncio
async def test_rerank_top_k_caps_request_and_response() -> None:
    runner = FakeVoyageRunner(results=[(0, 0.9), (1, 0.8), (2, 0.7)])
    reranker = VoyageReranker(runner=runner)
    results = await reranker.rerank("q", _candidates(), top_k=2)
    assert len(results) == 2
    assert runner.rerank_calls[0].top_k == 2


@pytest.mark.asyncio
async def test_rerank_top_k_none_forwards_full_count() -> None:
    runner = FakeVoyageRunner(results=[(0, 0.9), (1, 0.8), (2, 0.7)])
    reranker = VoyageReranker(runner=runner)
    await reranker.rerank("q", _candidates())
    assert runner.rerank_calls[0].top_k == 3


@pytest.mark.asyncio
async def test_rerank_empty_candidates_short_circuits() -> None:
    runner = FakeVoyageRunner()
    reranker = VoyageReranker(runner=runner)
    assert await reranker.rerank("q", []) == []
    assert runner.rerank_calls == []


@pytest.mark.asyncio
async def test_rerank_rejects_zero_top_k() -> None:
    reranker = VoyageReranker(runner=FakeVoyageRunner())
    with pytest.raises(ValueError, match="top_k"):
        await reranker.rerank("q", _candidates(), top_k=0)


@pytest.mark.asyncio
async def test_capabilities_advertised() -> None:
    reranker = VoyageReranker(runner=FakeVoyageRunner())
    assert reranker.capabilities() == {"managed", "batched"}


@pytest.mark.asyncio
async def test_close_propagates_to_runner() -> None:
    runner = FakeVoyageRunner()
    reranker = VoyageReranker(runner=runner)
    await reranker.close()
    assert runner.closed


@pytest.mark.asyncio
async def test_model_property_exposed() -> None:
    reranker = VoyageReranker(runner=FakeVoyageRunner(), model="rerank-2-lite")
    assert reranker.model == "rerank-2-lite"


@pytest.mark.asyncio
async def test_conformance_suite() -> None:
    runner = FakeVoyageRunner(results=[(0, 0.9), (1, 0.6), (2, 0.3)])
    reranker = VoyageReranker(runner=runner)
    await run_reranker_conformance(reranker)
