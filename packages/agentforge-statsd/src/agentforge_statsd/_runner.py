"""StatsD runner Protocol + production SDK wrapper.

The Protocol abstracts the three calls `StatsdHook` makes
(`incr`, `gauge`, `timing`) so unit tests can inject a fake
that records every emission and assert against it. The
production wrapper holds a `statsd.StatsClient` and forwards
directly.
"""

from __future__ import annotations

from typing import Any, Protocol


class StatsdRunner(Protocol):
    """Lifecycle Protocol for the three metric primitives we emit.

    The shape mirrors `statsd.StatsClient`'s API surface so the
    production runner is a thin pass-through; the in-memory
    fake (`FakeStatsdRunner`) records every call as a tuple
    for assertion.
    """

    def incr(self, key: str, count: int = 1) -> None:  # pragma: no cover
        """Increment a counter by ``count`` (default 1)."""
        ...

    def gauge(self, key: str, value: float) -> None:  # pragma: no cover
        """Set a gauge to ``value`` (replaces previous reading)."""
        ...

    def timing(self, key: str, ms: float) -> None:  # pragma: no cover
        """Record a duration in milliseconds."""
        ...

    def close(self) -> None:  # pragma: no cover
        """Release any held socket / connection."""
        ...


class _StatsClientRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``statsd.StatsClient``."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def incr(self, key: str, count: int = 1) -> None:
        self._client.incr(key, count)

    def gauge(self, key: str, value: float) -> None:
        self._client.gauge(key, value)

    def timing(self, key: str, ms: float) -> None:
        self._client.timing(key, ms)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()


__all__ = ["StatsdRunner"]
