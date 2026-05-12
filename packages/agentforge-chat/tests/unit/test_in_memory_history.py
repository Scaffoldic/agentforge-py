"""Unit tests for `InMemoryChatHistory`."""

from __future__ import annotations

import pytest
from agentforge_chat import InMemoryChatHistory
from agentforge_core.testing import run_chat_history_conformance


@pytest.mark.asyncio
async def test_in_memory_history_passes_conformance() -> None:
    await run_chat_history_conformance(InMemoryChatHistory())


@pytest.mark.asyncio
async def test_in_memory_history_supports_ttl_capability() -> None:
    store = InMemoryChatHistory()
    assert store.supports("ttl") is True
    assert store.supports("encryption_at_rest") is False
