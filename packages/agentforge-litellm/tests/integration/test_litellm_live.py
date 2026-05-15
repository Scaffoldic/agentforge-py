"""Live integration tests for `agentforge-litellm`. Gated behind `-m live`.

Routes via OpenAI by default (uses `OPENAI_API_KEY`). Set
`LITELLM_LIVE_MODEL` to test against another backend.
"""

from __future__ import annotations

import os

import pytest
from agentforge_core.values.messages import Message
from agentforge_litellm import LiteLLMClient

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_call_returns_text() -> None:  # pragma: no cover — live-only.
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    model = os.environ.get("LITELLM_LIVE_MODEL", "gpt-4o-mini")
    client = LiteLLMClient.from_config(model=model)
    try:
        resp = await client.call(
            system="Reply with one word.",
            messages=[Message(role="user", content="ping")],
        )
        assert resp.content
        assert resp.provider == "litellm"
    finally:
        await client.close()
