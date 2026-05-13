"""In-memory `StatsdRunner` for unit tests + downstream integration.

Records every metric call as a tagged tuple in `self.calls`:

- ``("incr", key, count)``
- ``("gauge", key, value)``
- ``("timing", key, ms)``

The fake lives in ``src/`` (not ``tests/``) so other packages
can import + reuse it for their own integration tests
(pattern from feat-020 v0.2).
"""

from __future__ import annotations


class FakeStatsdRunner:
    """In-memory recorder of every statsd call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []
        self.closed = False

    def incr(self, key: str, count: int = 1) -> None:
        self.calls.append(("incr", key, float(count)))

    def gauge(self, key: str, value: float) -> None:
        self.calls.append(("gauge", key, float(value)))

    def timing(self, key: str, ms: float) -> None:
        self.calls.append(("timing", key, float(ms)))

    def close(self) -> None:
        self.closed = True


__all__ = ["FakeStatsdRunner"]
