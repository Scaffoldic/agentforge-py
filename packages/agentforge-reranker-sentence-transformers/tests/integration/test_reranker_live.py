"""Live `SentenceTransformersReranker` integration test (feat-021).

Downloads ``cross-encoder/ms-marco-MiniLM-L-6-v2`` (~80MB) on
first run. Gated on `RUN_LIVE_RERANKER=1`. Run with:

    RUN_LIVE_RERANKER=1 \\
        uv run pytest -m live \\
        packages/agentforge-reranker-sentence-transformers/
"""

from __future__ import annotations

import os

import pytest
from agentforge_core.values.vector import VectorMatch


@pytest.mark.live
@pytest.mark.asyncio
async def test_reranker_live_reorders_known_candidates() -> None:
    if os.environ.get("RUN_LIVE_RERANKER") != "1":
        pytest.skip("RUN_LIVE_RERANKER != 1")

    from agentforge_reranker_sentence_transformers import (  # noqa: PLC0415
        SentenceTransformersReranker,
    )

    candidates = [
        VectorMatch(
            id="weather",
            text="The weather today is sunny and warm.",
            score=0.5,
            metadata={},
        ),
        VectorMatch(
            id="deploy",
            text="To deploy an agent, run `agentforge run` from your project root.",
            score=0.5,
            metadata={},
        ),
        VectorMatch(
            id="recipe",
            text="A classic pasta carbonara needs eggs, pancetta, and pepper.",
            score=0.5,
            metadata={},
        ),
    ]
    reranker = SentenceTransformersReranker.from_config()
    try:
        results = await reranker.rerank(
            "how do I deploy an agentforge agent?",
            candidates,
            top_k=3,
        )
    finally:
        await reranker.close()

    # The deploy candidate is the only relevant one for this query.
    assert results[0].id == "deploy"
    # All scores normalised into [0, 1] per the ABC contract.
    assert all(0.0 <= r.score <= 1.0 for r in results)
