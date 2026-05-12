"""Tiny LRU+TTL cache for per-session idempotency keys (feat-020).

Keyed by ``(session_id, key)``; values are the previous
`ChatResponse`. Entries past TTL are evicted on lookup; entries
past `max_entries` are evicted oldest-first.
"""

from __future__ import annotations

import time
from collections import OrderedDict


class IdempotencyCache[V]:
    def __init__(self, *, ttl_s: float, max_entries: int = 256) -> None:
        self._ttl = ttl_s
        self._max = max_entries
        self._store: OrderedDict[tuple[str, str], tuple[float, V]] = OrderedDict()

    def get(self, session_id: str, key: str) -> V | None:
        k = (session_id, key)
        entry = self._store.get(k)
        if entry is None:
            return None
        ts, value = entry
        if (time.monotonic() - ts) > self._ttl:
            self._store.pop(k, None)
            return None
        # Mark as recently used.
        self._store.move_to_end(k)
        return value

    def put(self, session_id: str, key: str, value: V) -> None:
        k = (session_id, key)
        self._store[k] = (time.monotonic(), value)
        self._store.move_to_end(k)
        while len(self._store) > self._max:
            self._store.popitem(last=False)
