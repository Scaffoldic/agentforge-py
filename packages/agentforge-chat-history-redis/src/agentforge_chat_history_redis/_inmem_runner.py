"""In-memory `RedisFakeRunner` for unit tests (feat-020 v0.2).

Emulates the narrow Redis command vocabulary `RedisChatHistory` +
`RedisSessionLock` rely on. Lives in `src/` so external packages
can reuse it.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any


class RedisFakeRunner:
    """In-memory emulation of `redis.asyncio.Redis` calls."""

    def __init__(self) -> None:
        self._kv: dict[str, tuple[str, float | None]] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._zsets: dict[str, dict[str, float]] = {}
        self._sets: dict[str, set[str]] = {}
        self.closed = False

    # ------------------------------------------------------------------
    # KV
    # ------------------------------------------------------------------

    async def set_kv(
        self,
        key: str,
        value: str,
        *,
        nx: bool = False,
        px: int | None = None,
    ) -> bool:
        existing = self._get_unexpired(key)
        if nx and existing is not None:
            return False
        expires_at = (time.monotonic() + px / 1000.0) if px is not None else None
        self._kv[key] = (value, expires_at)
        return True

    async def get(self, key: str) -> str | None:
        return self._get_unexpired(key)

    async def delete(self, *keys: str) -> int:
        n = 0
        for key in keys:
            if key in self._kv:
                del self._kv[key]
                n += 1
            if key in self._hashes:
                del self._hashes[key]
                n += 1
            if key in self._zsets:
                del self._zsets[key]
                n += 1
            if key in self._sets:
                del self._sets[key]
                n += 1
        return n

    # ------------------------------------------------------------------
    # Hashes
    # ------------------------------------------------------------------

    async def hset(self, key: str, mapping: dict[str, str]) -> None:
        if not mapping:
            return
        self._hashes.setdefault(key, {}).update(mapping)

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    # ------------------------------------------------------------------
    # Sorted sets
    # ------------------------------------------------------------------

    async def zadd(self, key: str, mapping: dict[str, float]) -> None:
        if not mapping:
            return
        self._zsets.setdefault(key, {}).update(mapping)

    async def zrange(self, key: str, start: int, end: int) -> list[str]:
        items = self._zsets.get(key, {})
        ordered = sorted(items, key=lambda m: items[m])
        if end == -1:
            return ordered[start:]
        return ordered[start : end + 1]

    async def zrangebyscore(
        self,
        key: str,
        min_score: float,
        max_score: float,
    ) -> list[str]:
        items = self._zsets.get(key, {})
        return sorted(
            (m for m, s in items.items() if min_score <= s <= max_score),
            key=lambda m: items[m],
        )

    # ------------------------------------------------------------------
    # Sets
    # ------------------------------------------------------------------

    async def sadd(self, key: str, *members: str) -> None:
        if not members:
            return
        self._sets.setdefault(key, set()).update(members)

    async def smembers(self, key: str) -> set[str]:
        return set(self._sets.get(key, set()))

    async def srem(self, key: str, *members: str) -> int:
        if not members or key not in self._sets:
            return 0
        before = len(self._sets[key])
        self._sets[key] -= set(members)
        return before - len(self._sets[key])

    # ------------------------------------------------------------------
    # Other
    # ------------------------------------------------------------------

    async def expire(self, key: str, seconds: int) -> None:
        # The fake doesn't time-out keys actively; tests asserting TTL
        # use the kv expiry path inside set_kv.
        del key, seconds

    def scan_iter(self, match: str) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            for key in list(self._hashes) + list(self._kv):
                if _match(match, key):
                    yield key

        return _gen()

    async def eval(self, script: str, num_keys: int, *keys_and_args: str) -> Any:
        del script, num_keys
        # Unlock-Lua emulation: del key IFF stored value == token.
        key = keys_and_args[0]
        token = keys_and_args[1]
        stored = self._get_unexpired(key)
        if stored == token:
            self._kv.pop(key, None)
            return 1
        return 0

    async def close(self) -> None:
        self.closed = True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_unexpired(self, key: str) -> str | None:
        entry = self._kv.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.monotonic() >= expires_at:
            del self._kv[key]
            return None
        return value


def _match(pattern: str, key: str) -> bool:  # pragma: no cover — defensive
    """Tiny glob matcher: supports trailing ``*`` and exact match."""
    if pattern.endswith("*"):
        return key.startswith(pattern[:-1])
    return key == pattern


async def park_for(seconds: float) -> None:  # pragma: no cover — helper for tests
    await asyncio.sleep(seconds)


__all__ = ["RedisFakeRunner"]
