"""Live integration tests for `agentforge-ollama`. Gated behind `-m live`.

Requires a running local Ollama daemon and at least one pulled
model. Set `OLLAMA_LIVE_MODEL` to the model name to test.
"""

from __future__ import annotations

import os

import pytest
from agentforge_core.values.messages import Message
from agentforge_ollama import OllamaClient

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_call_returns_text() -> None:  # pragma: no cover — live-only.
    model = os.environ.get("OLLAMA_LIVE_MODEL")
    if not model:
        pytest.skip("OLLAMA_LIVE_MODEL not set")
    client = OllamaClient.from_config(model=model)
    try:
        resp = await client.call(
            system="Reply with one word.",
            messages=[Message(role="user", content="ping")],
        )
        assert resp.content
        assert resp.provider == "ollama"
    finally:
        await client.close()
