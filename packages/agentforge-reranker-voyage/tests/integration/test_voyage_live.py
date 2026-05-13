"""Live `VoyageReranker` integration test (feat-021 vendor follow-up)."""

from __future__ import annotations

import os

import pytest
from agentforge_core.values.vector import VectorMatch


@pytest.mark.live
@pytest.mark.asyncio
async def test_voyage_live_reorders_known_candidates() -> None:
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        pytest.skip("VOYAGE_API_KEY not set")

    from agentforge_reranker_voyage import VoyageReranker  # noqa: PLC0415

    candidates = [
        VectorMatch(id="weather", text="The weather today is sunny.", score=0.5, metadata={}),
        VectorMatch(
            id="deploy",
            text="To deploy an agent, run `agentforge run` from your project root.",
            score=0.5,
            metadata={},
        ),
        VectorMatch(
            id="recipe",
            text="Pasta carbonara needs eggs, pancetta, and pepper.",
            score=0.5,
            metadata={},
        ),
    ]
    reranker = VoyageReranker.from_config(api_key=api_key)
    try:
        results = await reranker.rerank(
            "how do I deploy an agentforge agent?",
            candidates,
            top_k=3,
        )
    finally:
        await reranker.close()

    assert results[0].id == "deploy"
    assert all(0.0 <= r.score <= 1.0 for r in results)
