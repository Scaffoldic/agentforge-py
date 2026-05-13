"""Unit tests for `RedisSessionLock`."""

from __future__ import annotations

import asyncio

import pytest
from agentforge_chat_history_redis import (
    RedisSessionLock,
    redis_session_lock_factory,
)
from agentforge_chat_history_redis._inmem_runner import RedisFakeRunner


@pytest.mark.asyncio
async def test_redis_lock_round_trip() -> None:
    runner = RedisFakeRunner()
    lock = RedisSessionLock("s1", runner=runner, ttl_s=1.0)
    async with lock:
        assert await runner.get("chat:lock:s1") is not None
    # After release the key is gone — the Lua unlock script ran.
    assert await runner.get("chat:lock:s1") is None


@pytest.mark.asyncio
async def test_redis_lock_blocks_until_release() -> None:
    runner = RedisFakeRunner()
    first = RedisSessionLock("s1", runner=runner, ttl_s=5.0)
    second = RedisSessionLock("s1", runner=runner, ttl_s=5.0, retry_delay_s=0.01)
    events: list[str] = []

    async def second_holder() -> None:
        events.append("second-waiting")
        async with second:
            events.append("second-acquired")

    async with first:
        events.append("first-acquired")
        task = asyncio.create_task(second_holder())
        await asyncio.sleep(0.05)
        # Second is still waiting; first holds the lock.
        assert "second-acquired" not in events
        events.append("first-releasing")
    await asyncio.wait_for(task, timeout=2.0)
    assert events[-1] == "second-acquired"


@pytest.mark.asyncio
async def test_factory_builds_session_specific_locks() -> None:
    runner = RedisFakeRunner()
    factory = redis_session_lock_factory(runner, ttl_s=1.0)
    lock_a = factory("a")
    lock_b = factory("b")
    async with lock_a, lock_b:
        # Distinct keys — both acquired simultaneously.
        assert await runner.get("chat:lock:a") is not None
        assert await runner.get("chat:lock:b") is not None
