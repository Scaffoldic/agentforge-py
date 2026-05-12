"""Per-session lock registry (feat-020).

`ChatSession.send`/`stream` acquires a session-scoped
`asyncio.Lock` so concurrent calls against the same `session_id`
queue. Locks live in a `WeakValueDictionary`; once no session
references a key the lock GCs automatically.

v0.2 is single-process. Cross-process locking (Redis-backed) is
v0.3.
"""

from __future__ import annotations

import asyncio
import weakref


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
    """Return the (shared, weak-referenced) lock for ``session_id``."""
    return _REGISTRY.get(session_id)
