"""Internal redis-runner abstraction.

`RedisChatHistory` always goes through one of these — never the
Redis client directly — so unit tests inject a `RedisFakeRunner`
that emulates the narrow command vocabulary the driver emits.
Mirrors the pattern in `agentforge-memory-postgres/_runner.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class RedisRunner(Protocol):  # pragma: no cover — Protocol method stubs
    """Thin slice of `redis.asyncio.Redis` we depend on."""

    async def set_kv(
        self,
        key: str,
        value: str,
        *,
        nx: bool = False,
        px: int | None = None,
    ) -> bool: ...

    async def get(self, key: str) -> str | None: ...

    async def delete(self, *keys: str) -> int: ...

    async def hset(self, key: str, mapping: dict[str, str]) -> None: ...

    async def hgetall(self, key: str) -> dict[str, str]: ...

    async def zadd(self, key: str, mapping: dict[str, float]) -> None: ...

    async def zrange(self, key: str, start: int, end: int) -> list[str]: ...

    async def zrangebyscore(
        self,
        key: str,
        min_score: float,
        max_score: float,
    ) -> list[str]: ...

    async def sadd(self, key: str, *members: str) -> None: ...

    async def smembers(self, key: str) -> set[str]: ...

    async def srem(self, key: str, *members: str) -> int: ...

    async def expire(self, key: str, seconds: int) -> None: ...

    def scan_iter(self, match: str) -> AsyncIterator[str]: ...

    async def eval(self, script: str, num_keys: int, *keys_and_args: str) -> Any: ...

    async def close(self) -> None: ...


class _RedisClientRunner:  # pragma: no cover — exercised only with `-m live`
    """Production runner wrapping `redis.asyncio.Redis`."""

    def __init__(self, client: Any) -> None:
        self._c = client

    async def set_kv(
        self,
        key: str,
        value: str,
        *,
        nx: bool = False,
        px: int | None = None,
    ) -> bool:
        result = await self._c.set(key, value, nx=nx, px=px)
        return bool(result)

    async def get(self, key: str) -> str | None:
        value = await self._c.get(key)
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    async def delete(self, *keys: str) -> int:
        return int(await self._c.delete(*keys))

    async def hset(self, key: str, mapping: dict[str, str]) -> None:
        if mapping:
            await self._c.hset(key, mapping=mapping)

    async def hgetall(self, key: str) -> dict[str, str]:
        raw = await self._c.hgetall(key)
        return {_decode(k): _decode(v) for k, v in raw.items()}

    async def zadd(self, key: str, mapping: dict[str, float]) -> None:
        if mapping:
            await self._c.zadd(key, mapping)

    async def zrange(self, key: str, start: int, end: int) -> list[str]:
        raw = await self._c.zrange(key, start, end)
        return [_decode(v) for v in raw]

    async def zrangebyscore(
        self,
        key: str,
        min_score: float,
        max_score: float,
    ) -> list[str]:
        raw = await self._c.zrangebyscore(key, min_score, max_score)
        return [_decode(v) for v in raw]

    async def sadd(self, key: str, *members: str) -> None:
        if members:
            await self._c.sadd(key, *members)

    async def smembers(self, key: str) -> set[str]:
        raw = await self._c.smembers(key)
        return {_decode(v) for v in raw}

    async def srem(self, key: str, *members: str) -> int:
        if not members:
            return 0
        return int(await self._c.srem(key, *members))

    async def expire(self, key: str, seconds: int) -> None:
        await self._c.expire(key, seconds)

    def scan_iter(self, match: str) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            async for raw in self._c.scan_iter(match=match):
                yield _decode(raw)

        return _gen()

    async def eval(self, script: str, num_keys: int, *keys_and_args: str) -> Any:
        return await self._c.eval(script, num_keys, *keys_and_args)

    async def close(self) -> None:
        await self._c.aclose()


def _decode(value: Any) -> str:  # pragma: no cover — exercised via live
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


__all__ = ["RedisRunner"]
