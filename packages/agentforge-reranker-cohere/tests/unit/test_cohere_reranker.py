"""Unit tests for `CohereReranker` (feat-021 vendor follow-up)."""

from __future__ import annotations

import pytest
from agentforge_core.testing import run_reranker_conformance
from agentforge_core.values.vector import VectorMatch
from agentforge_reranker_cohere import CohereReranker
from agentforge_reranker_cohere._inmem_runner import FakeCohereRunner


def _candidates() -> list[VectorMatch]:
    return [
        VectorMatch(id="a", text="alpha", score=0.5, metadata={"i": 0}),
        VectorMatch(id="b", text="beta", score=0.5, metadata={"i": 1}),
        VectorMatch(id="c", text="gamma", score=0.5, metadata={"i": 2}),
    ]


@pytest.mark.asyncio
async def test_rerank_sorts_per_api_response_order() -> None:
    # Cohere returns results in descending score order; we trust the
    # API order and use the (index, score) tuples directly.
    runner = FakeCohereRunner(results=[(2, 0.95), (0, 0.7), (1, 0.2)])
    reranker = CohereReranker(runner=runner, model="rerank-english-v3.0")

    results = await reranker.rerank("q", _candidates())

    assert [r.id for r in results] == ["c", "a", "b"]
    assert results[0].score == 0.95
    assert results[0].text == "gamma"
    assert results[0].metadata == {"i": 2}


@pytest.mark.asyncio
async def test_rerank_clamps_out_of_range_scores_defensively() -> None:
    runner = FakeCohereRunner(results=[(0, 1.5), (1, -0.2), (2, 0.5)])
    reranker = CohereReranker(runner=runner)
    results = await reranker.rerank("q", _candidates())
    assert all(0.0 <= r.score <= 1.0 for r in results)
    assert results[0].score == 1.0
    assert results[1].score == 0.0


@pytest.mark.asyncio
async def test_rerank_top_k_caps_request_and_response() -> None:
    runner = FakeCohereRunner(results=[(0, 0.9), (1, 0.8), (2, 0.7)])
    reranker = CohereReranker(runner=runner)
    results = await reranker.rerank("q", _candidates(), top_k=2)
    assert len(results) == 2
    # Server-side top_n forwarded as the requested top_k.
    assert runner.rerank_calls[0].top_n == 2


@pytest.mark.asyncio
async def test_rerank_top_k_none_forwards_full_pool_count() -> None:
    runner = FakeCohereRunner(results=[(0, 0.9), (1, 0.8), (2, 0.7)])
    reranker = CohereReranker(runner=runner)
    await reranker.rerank("q", _candidates())
    # When the caller wants every candidate, pass the full count
    # (Cohere otherwise defaults to caller-truncation).
    assert runner.rerank_calls[0].top_n == 3


@pytest.mark.asyncio
async def test_rerank_empty_candidates_short_circuits() -> None:
    runner = FakeCohereRunner()
    reranker = CohereReranker(runner=runner)
    assert await reranker.rerank("q", []) == []
    assert runner.rerank_calls == []


@pytest.mark.asyncio
async def test_rerank_rejects_zero_top_k() -> None:
    reranker = CohereReranker(runner=FakeCohereRunner())
    with pytest.raises(ValueError, match="top_k"):
        await reranker.rerank("q", _candidates(), top_k=0)


@pytest.mark.asyncio
async def test_capabilities_advertised() -> None:
    reranker = CohereReranker(runner=FakeCohereRunner())
    assert reranker.capabilities() == {"managed", "batched"}
    assert reranker.supports("managed") is True
    assert reranker.supports("local") is False


@pytest.mark.asyncio
async def test_close_propagates_to_runner() -> None:
    runner = FakeCohereRunner()
    reranker = CohereReranker(runner=runner)
    await reranker.close()
    assert runner.closed


@pytest.mark.asyncio
async def test_model_property_exposed() -> None:
    reranker = CohereReranker(runner=FakeCohereRunner(), model="rerank-multilingual-v3.0")
    assert reranker.model == "rerank-multilingual-v3.0"


@pytest.mark.asyncio
async def test_conformance_suite() -> None:
    # The conformance suite calls rerank() with varying candidate-list
    # sizes; supply enough scripted results to satisfy each call.
    runner = FakeCohereRunner(results=[(0, 0.9), (1, 0.6), (2, 0.3)])
    reranker = CohereReranker(runner=runner)
    await run_reranker_conformance(reranker)
