"""In-memory `LangfuseRunner` for unit tests + downstream integration.

Records calls as tagged tuples on the instance, keyed by
``run_id`` so tests can assert against the full trace shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class _TraceRecord:
    name: str
    run_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    spans: list[dict[str, Any]] = field(default_factory=list)
    scores: list[dict[str, Any]] = field(default_factory=list)
    flushed: bool = False


class FakeLangfuseRunner:
    """In-memory recorder of every Langfuse call."""

    def __init__(self) -> None:
        self.traces: dict[str, _TraceRecord] = {}
        self.closed = False

    def open_trace(
        self,
        *,
        name: str,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self.traces[run_id] = _TraceRecord(
            name=name,
            run_id=run_id,
            metadata=dict(metadata or {}),
        )
        return run_id

    def add_span(
        self,
        *,
        trace_id: str,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        rec = self.traces.get(trace_id)
        if rec is None:
            return
        rec.spans.append({"name": name, "metadata": dict(metadata or {})})

    def add_score(
        self,
        *,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        rec = self.traces.get(trace_id)
        if rec is None:
            return
        rec.scores.append({"name": name, "value": float(value), "comment": comment})

    def flush(self, *, trace_id: str) -> None:
        rec = self.traces.get(trace_id)
        if rec is not None:
            rec.flushed = True

    def close(self) -> None:
        self.closed = True


__all__ = ["FakeLangfuseRunner"]
