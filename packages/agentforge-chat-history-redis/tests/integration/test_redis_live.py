"""Live integration tests for Redis chat history + lock (feat-020 v0.2).

Gated by `@pytest.mark.live` + `REDIS_URL` env var.

Boot a local Redis with:

    docker run --rm -d -p 6379:6379 redis:7
    REDIS_URL=redis://localhost:6379 \
      uv run pytest -m live packages/agentforge-chat-history-redis/
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from agentforge_chat_history_redis import RedisChatHistory, RedisSessionLock
from agentforge_chat_history_redis._runner import _RedisClientRunner
from agentforge_core.testing import run_chat_history_conformance


def _make_runner() -> _RedisClientRunner:
    import redis.asyncio as redis_asyncio  # noqa: PLC0415

    url = os.environ["REDIS_URL"]
    return _RedisClientRunner(redis_asyncio.Redis.from_url(url))


@pytest.mark.live
@pytest.mark.asyncio
async def test_redis_chat_history_live_conformance() -> None:
    if not os.environ.get("REDIS_URL"):
        pytest.skip("REDIS_URL unset; skipping")
    runner = _make_runner()
    store = RedisChatHistory(runner=runner)
    try:
        await run_chat_history_conformance(store)
    finally:
        await store.close()


@pytest.mark.live
@pytest.mark.asyncio
async def test_redis_lock_parallel_acquire() -> None:
    if not os.environ.get("REDIS_URL"):
        pytest.skip("REDIS_URL unset; skipping")
    runner = _make_runner()
    sid = f"live-{uuid.uuid4().hex[:8]}"
    first = RedisSessionLock(sid, runner=runner, ttl_s=5.0)
    second = RedisSessionLock(sid, runner=runner, ttl_s=5.0, retry_delay_s=0.05)
    events: list[str] = []

    async def hold_second() -> None:
        async with second:
            events.append("second")

    try:
        async with first:
            events.append("first")
            task = asyncio.create_task(hold_second())
            await asyncio.sleep(0.2)
            assert events == ["first"]
        await asyncio.wait_for(task, timeout=3.0)
        assert events == ["first", "second"]
    finally:
        await runner.close()
