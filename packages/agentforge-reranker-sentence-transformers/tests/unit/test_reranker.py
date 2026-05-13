"""Unit tests for `SentenceTransformersReranker` (feat-021)."""

from __future__ import annotations

import pytest
from agentforge_core.testing import run_reranker_conformance
from agentforge_core.values.vector import VectorMatch
from agentforge_reranker_sentence_transformers import SentenceTransformersReranker
from agentforge_reranker_sentence_transformers._inmem_runner import (
    FakeCrossEncoderRunner,
)
from agentforge_reranker_sentence_transformers.reranker import _sigmoid

SIGMOID_TOLERANCE = 1e-3


def _candidates() -> list[VectorMatch]:
    """Three deterministic candidates for the unit tests."""
    return [
        VectorMatch(id="a", text="alpha", score=0.7, metadata={"i": 0}),
        VectorMatch(id="b", text="beta", score=0.6, metadata={"i": 1}),
        VectorMatch(id="c", text="gamma", score=0.5, metadata={"i": 2}),
    ]


def test_sigmoid_anchors_match_intuition() -> None:
    """Raw -10 → ~0, raw 0 → 0.5, raw +10 → ~1."""
    assert abs(_sigmoid(-10.0) - 0.0) < SIGMOID_TOLERANCE
    assert abs(_sigmoid(0.0) - 0.5) < SIGMOID_TOLERANCE
    assert abs(_sigmoid(10.0) - 1.0) < SIGMOID_TOLERANCE
    # Monotonic
    assert _sigmoid(-1.0) < _sigmoid(0.0) < _sigmoid(1.0)


@pytest.mark.asyncio
async def test_rerank_sorts_descending_by_normalised_score() -> None:
    # Raw scores: a -> low, b -> medium, c -> high. Expected order
    # after rerank: c, b, a.
    runner = FakeCrossEncoderRunner(scores=[-5.0, 0.0, 5.0])
    reranker = SentenceTransformersReranker(runner=runner)

    results = await reranker.rerank("q", _candidates())

    assert [r.id for r in results] == ["c", "b", "a"]
    # Each score normalised into [0, 1] and matches sigmoid of raw.
    assert abs(results[0].score - _sigmoid(5.0)) < SIGMOID_TOLERANCE
    assert abs(results[1].score - _sigmoid(0.0)) < SIGMOID_TOLERANCE
    assert abs(results[2].score - _sigmoid(-5.0)) < SIGMOID_TOLERANCE


@pytest.mark.asyncio
async def test_rerank_preserves_other_fields() -> None:
    runner = FakeCrossEncoderRunner(scores=[0.0, 0.0, 0.0])
    reranker = SentenceTransformersReranker(runner=runner)
    results = await reranker.rerank("q", _candidates())
    by_id = {r.id: r for r in results}
    assert by_id["a"].text == "alpha"
    assert by_id["b"].metadata == {"i": 1}


@pytest.mark.asyncio
async def test_rerank_top_k_truncates() -> None:
    runner = FakeCrossEncoderRunner(scores=[1.0, 2.0, 3.0])
    reranker = SentenceTransformersReranker(runner=runner)
    results = await reranker.rerank("q", _candidates(), top_k=2)
    assert len(results) == 2
    # Best two are c (raw 3.0) and b (raw 2.0).
    assert [r.id for r in results] == ["c", "b"]


@pytest.mark.asyncio
async def test_rerank_empty_candidates_short_circuits() -> None:
    runner = FakeCrossEncoderRunner(scores=[])
    reranker = SentenceTransformersReranker(runner=runner)
    assert await reranker.rerank("q", []) == []
    # No predict call when there's nothing to score.
    assert runner.predict_calls == []


@pytest.mark.asyncio
async def test_rerank_rejects_zero_top_k() -> None:
    reranker = SentenceTransformersReranker(runner=FakeCrossEncoderRunner())
    with pytest.raises(ValueError, match="top_k"):
        await reranker.rerank("q", _candidates(), top_k=0)


@pytest.mark.asyncio
async def test_capabilities_advertised() -> None:
    reranker = SentenceTransformersReranker(runner=FakeCrossEncoderRunner())
    assert reranker.capabilities() == {"local", "batched"}
    assert reranker.supports("local") is True
    assert reranker.supports("managed") is False


@pytest.mark.asyncio
async def test_runner_score_count_mismatch_raises() -> None:
    """Defensive: if the runner returns the wrong number of scores
    we surface a clear error rather than silently mis-zipping."""
    runner = FakeCrossEncoderRunner()
    # set_scores intentionally too short to force the mismatch.
    runner.set_scores([1.0, 2.0])

    reranker = SentenceTransformersReranker(runner=runner)
    # FakeCrossEncoderRunner itself raises before we get to the
    # length check in the reranker, which is also acceptable.
    with pytest.raises((RuntimeError, ValueError)):
        await reranker.rerank("q", _candidates())


@pytest.mark.asyncio
async def test_close_propagates_to_runner() -> None:
    runner = FakeCrossEncoderRunner()
    reranker = SentenceTransformersReranker(runner=runner)
    await reranker.close()
    assert runner.closed


@pytest.mark.asyncio
async def test_conformance_suite() -> None:
    # Conformance probes call predict() under several different
    # candidate-list sizes; supply enough scores up-front and rely on
    # FakeCrossEncoderRunner's prefix-slicing.
    runner = FakeCrossEncoderRunner(scores=[3.0, 2.0, 1.0])
    reranker = SentenceTransformersReranker(runner=runner)
    await run_reranker_conformance(reranker)
