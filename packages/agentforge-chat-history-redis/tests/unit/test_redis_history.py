"""Unit tests for `RedisChatHistory` against the fake runner."""

from __future__ import annotations

import pytest
from agentforge_chat_history_redis import RedisChatHistory
from agentforge_chat_history_redis._inmem_runner import RedisFakeRunner
from agentforge_core.testing import run_chat_history_conformance


@pytest.mark.asyncio
async def test_redis_chat_history_satisfies_conformance() -> None:
    runner = RedisFakeRunner()
    store = await RedisChatHistory.from_url("redis://fake", runner=runner)
    await run_chat_history_conformance(store)
    await store.close()
    assert runner.closed is True


@pytest.mark.asyncio
async def test_redis_chat_history_capabilities() -> None:
    runner = RedisFakeRunner()
    store = await RedisChatHistory.from_url("redis://fake", runner=runner)
    assert store.capabilities() == {"ttl", "streaming_load"}
    await store.close()
