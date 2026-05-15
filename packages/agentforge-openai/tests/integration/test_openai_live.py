"""Live integration tests for `agentforge-openai`. Gated behind `-m live`."""

from __future__ import annotations

import os

import pytest
from agentforge_core.values.messages import Message
from agentforge_openai import OpenAIClient, OpenAIEmbeddingClient

pytestmark = pytest.mark.live


def _live_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set")
    return key


@pytest.mark.asyncio
async def test_live_chat_returns_text() -> None:  # pragma: no cover — live-only.
    key = _live_key()
    client = OpenAIClient.from_config(model="gpt-4o-mini", api_key=key)
    try:
        resp = await client.call(
            system="Reply with one word.",
            messages=[Message(role="user", content="ping")],
        )
        assert resp.content
        assert resp.provider == "openai"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_live_embedding_returns_vector() -> None:  # pragma: no cover — live-only.
    key = _live_key()
    client = OpenAIEmbeddingClient.from_config(
        model="text-embedding-3-small",
        api_key=key,
    )
    try:
        resp = await client.embed(["hello"])
        assert len(resp.vectors) == 1
        assert resp.dimensions == 1536
    finally:
        await client.close()
