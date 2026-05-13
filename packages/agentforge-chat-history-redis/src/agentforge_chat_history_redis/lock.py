"""`RedisSessionLock` — cross-process per-session lock for chat-http
multi-worker deployments (feat-020 v0.2).

Implements the `SessionLock` Protocol from `agentforge_chat._locks`.
Uses the simple `SET key value NX PX <ttl_ms>` + UUID-fencing pattern:

- `__aenter__` retries `SET NX PX` until the key is acquired, storing
  a UUID4 token under the key as the fencing value.
- `__aexit__` runs a Lua script that deletes the key only if the
  stored value matches our token — avoids releasing someone else's
  lock after a TTL expiry.

Multi-cluster Redlock is v0.3+. Single-cluster Redis is enough for
the typical chat-http deployment (1-N workers sharing one cache).
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import TYPE_CHECKING
from uuid import uuid4

from agentforge_chat_history_redis._runner import RedisRunner

if TYPE_CHECKING:
    from agentforge_chat._locks import SessionLock, SessionLockFactory

_LOCK_KEY = "chat:lock:{}"
_UNLOCK_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) else return 0 end"
)


class RedisSessionLock:
    """Cross-process per-session lock backed by Redis.

    Conforms structurally to `agentforge_chat._locks.SessionLock`.
    """

    def __init__(
        self,
        session_id: str,
        *,
        runner: RedisRunner,
        ttl_s: float = 30.0,
        retry_delay_s: float = 0.05,
    ) -> None:
        self._session_id = session_id
        self._r = runner
        self._ttl_ms = int(ttl_s * 1000)
        self._retry_delay_s = retry_delay_s
        self._token = uuid4().hex
        self._key = _LOCK_KEY.format(session_id)

    async def __aenter__(self) -> RedisSessionLock:
        while True:
            acquired = await self._r.set_kv(self._key, self._token, nx=True, px=self._ttl_ms)
            if acquired:
                return self
            await asyncio.sleep(self._retry_delay_s)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._r.eval(_UNLOCK_LUA, 1, self._key, self._token)


def redis_session_lock_factory(
    runner: RedisRunner,
    *,
    ttl_s: float = 30.0,
    retry_delay_s: float = 0.05,
) -> SessionLockFactory:
    """Build a `SessionLockFactory` backed by ``runner``.

    Pass the resulting factory to
    `ChatSession(..., session_lock_factory=factory)` or
    `ChatServer(..., session_lock_factory=factory)` to enable
    cross-process per-session locking.
    """

    def _build(session_id: str) -> SessionLock:
        return RedisSessionLock(
            session_id,
            runner=runner,
            ttl_s=ttl_s,
            retry_delay_s=retry_delay_s,
        )

    return _build


__all__ = ["RedisSessionLock", "redis_session_lock_factory"]
