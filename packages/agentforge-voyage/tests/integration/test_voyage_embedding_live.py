"""Live integration tests for `agentforge-voyage`. Gated behind `-m live`."""

from __future__ import annotations

import os

import pytest
from agentforge_voyage import VoyageEmbeddingClient

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_embed_returns_vector() -> None:  # pragma: no cover — live-only.
    key = os.environ.get("VOYAGE_API_KEY")
    if not key:
        pytest.skip("VOYAGE_API_KEY not set")
    client = VoyageEmbeddingClient.from_config(model="voyage-3-lite", api_key=key)
    try:
        resp = await client.embed(["hello"])
        assert len(resp.vectors) == 1
        assert resp.dimensions == 512
    finally:
        await client.close()
