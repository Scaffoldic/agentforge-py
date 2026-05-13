"""Live `CohereReranker` integration test (feat-021 vendor follow-up).

Gated on ``COHERE_API_KEY``. Run with:

    COHERE_API_KEY=... \\
        uv run pytest -m live packages/agentforge-reranker-cohere/
"""

from __future__ import annotations

import os

import pytest
from agentforge_core.values.vector import VectorMatch


@pytest.mark.live
@pytest.mark.asyncio
async def test_cohere_live_reorders_known_candidates() -> None:
    api_key = os.environ.get("COHERE_API_KEY")
    if not api_key:
        pytest.skip("COHERE_API_KEY not set")

    from agentforge_reranker_cohere import CohereReranker  # noqa: PLC0415

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
    reranker = CohereReranker.from_config(api_key=api_key)
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
