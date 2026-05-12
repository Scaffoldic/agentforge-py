"""Per-session lock registry (feat-020).

`ChatSession.send` / `stream` acquires a session-scoped lock so
concurrent calls against the same `session_id` queue. v0.1 shipped
an in-process `asyncio.Lock` via `WeakValueDictionary`. v0.2 extends
the surface to support cross-process locks (Redis-backed) via a
`SessionLock` Protocol that both shapes satisfy.

Default factory keeps the in-process behaviour. Multi-worker
deployments inject `redis_session_lock_factory(...)` from
`agentforge-chat-history-redis`.
"""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import Callable
from types import TracebackType
from typing import Protocol


class SessionLock(Protocol):  # pragma: no cover — Protocol method stubs
    """Async-context-manager lock keyed by `session_id`.

    `ChatSession` calls `async with lock:` once per turn.
    Implementations:

    - :class:`InMemorySessionLock` — wraps a per-session
      ``asyncio.Lock``. Default; single-process only.
    - ``RedisSessionLock`` (in `agentforge-chat-history-redis`) —
      cross-process; uses Redis ``SET NX PX`` + UUID fencing.
    """

    async def __aenter__(self) -> SessionLock: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


SessionLockFactory = Callable[[str], SessionLock]
"""Build a `SessionLock` for one ``session_id``. v0.2 lets callers
inject this on `ChatSession` / `ChatServer` construction."""


class InMemorySessionLock:
    """Wraps a per-session `asyncio.Lock` so multiple chat turns on
    the same session_id queue inside one process.

    Conforms structurally to `SessionLock`.
    """

    def __init__(self, lock: asyncio.Lock) -> None:
        self._lock = lock

    async def __aenter__(self) -> InMemorySessionLock:
        await self._lock.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._lock.release()


class _LockRegistry:
    def __init__(self) -> None:
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

    def get(self, session_id: str) -> asyncio.Lock:
        lock = self._locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[session_id] = lock
        return lock


_REGISTRY = _LockRegistry()


def lock_for(session_id: str) -> asyncio.Lock:
    """Return the (shared, weak-referenced) raw `asyncio.Lock`.

    Retained for backward-compatibility with v0.1 callers that read
    `ChatSession._lock` directly. New code should use
    :func:`default_session_lock_factory` or inject a custom
    `SessionLockFactory`.
    """
    return _REGISTRY.get(session_id)


def default_session_lock_factory(session_id: str) -> SessionLock:
    """Build the default in-process `SessionLock` for ``session_id``.

    Wraps the shared `asyncio.Lock` from the weak-ref registry so
    multiple `ChatSession` instances bound to the same session_id
    still queue correctly.
    """
    return InMemorySessionLock(_REGISTRY.get(session_id))


__all__ = [
    "InMemorySessionLock",
    "SessionLock",
    "SessionLockFactory",
    "default_session_lock_factory",
    "lock_for",
]
