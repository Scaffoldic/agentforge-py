"""Live integration tests for `AnthropicClient`. Gated behind `-m live`.

Requires `ANTHROPIC_API_KEY` in the environment. Hits the real
Anthropic API — keep the requests tiny.
"""

from __future__ import annotations

import os

import pytest
from agentforge_anthropic import AnthropicClient
from agentforge_core.values.messages import Message

pytestmark = pytest.mark.live


def _live_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


@pytest.mark.asyncio
async def test_live_call_returns_text() -> None:  # pragma: no cover — live-only.
    key = _live_api_key()
    client = AnthropicClient.from_config(
        model="claude-haiku-4-5",
        api_key=key,
        max_tokens=64,
    )
    try:
        resp = await client.call(
            system="Reply with one word.",
            messages=[Message(role="user", content="ping")],
        )
        assert resp.content
        assert resp.usage.input_tokens > 0
        assert resp.provider == "anthropic"
    finally:
        await client.close()
