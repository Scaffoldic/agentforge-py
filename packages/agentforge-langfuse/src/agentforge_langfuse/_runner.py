"""Langfuse runner Protocol + production SDK wrapper.

The Protocol abstracts the calls `LangfuseHook` makes so unit
tests don't need the SDK in the dev venv. Production
`_LangfuseClientRunner` wraps a `langfuse.Langfuse` client
under `# pragma: no cover`.
"""

from __future__ import annotations

from typing import Any, Protocol


class LangfuseRunner(Protocol):
    """Lifecycle Protocol for Langfuse trace + span emissions."""

    def open_trace(
        self,
        *,
        name: str,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:  # pragma: no cover
        """Open a trace and return the trace_id used by subsequent calls."""
        ...

    def add_span(
        self,
        *,
        trace_id: str,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:  # pragma: no cover
        """Add a span under the named trace."""
        ...

    def add_score(
        self,
        *,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:  # pragma: no cover
        """Score the trace on a named dimension (cost, duration, ...)."""
        ...

    def flush(self, *, trace_id: str) -> None:  # pragma: no cover
        """Force the SDK's batch buffer to drain for ``trace_id``."""
        ...

    def close(self) -> None:  # pragma: no cover
        """Release the underlying SDK client."""
        ...


class _LangfuseClientRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``langfuse.Langfuse``."""

    def __init__(self, client: Any) -> None:
        self._client = client
        # Langfuse SDK creates trace handles lazily; we cache the
        # objects keyed by our caller-side trace_id (== run_id) so
        # subsequent add_span / add_score calls can target them.
        self._traces: dict[str, Any] = {}

    def open_trace(
        self,
        *,
        name: str,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        trace = self._client.trace(
            name=name,
            id=run_id,
            metadata=dict(metadata or {}),
        )
        self._traces[run_id] = trace
        return run_id

    def add_span(
        self,
        *,
        trace_id: str,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        trace = self._traces.get(trace_id)
        if trace is None:
            return
        trace.span(name=name, metadata=dict(metadata or {}))

    def add_score(
        self,
        *,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        trace = self._traces.get(trace_id)
        if trace is None:
            return
        trace.score(name=name, value=value, comment=comment)

    def flush(self, *, trace_id: str) -> None:
        flush = getattr(self._client, "flush", None)
        if callable(flush):
            flush()
        # Drop the local handle once flushed.
        self._traces.pop(trace_id, None)

    def close(self) -> None:
        shutdown = getattr(self._client, "shutdown", None)
        if callable(shutdown):
            shutdown()


__all__ = ["LangfuseRunner"]
