"""Cassette analysis helpers (feat-016 chunk 4).

`analyze_recording(path)` returns a `RecordingStats` summary about
a JSONL cassette produced by `agentforge.testing.record_llm`:

- total call count
- input + output token totals
- distinct tool calls observed
- per-call cost summary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentforge.testing.recording import load_recording


@dataclass(frozen=True)
class RecordingStats:
    """Summary of a captured LLM transcript."""

    call_count: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    tool_call_names: dict[str, int]
    redactions: list[str] = field(default_factory=list)
    format_version: int = 1


def analyze_recording(path: str | Path) -> RecordingStats:
    """Walk a cassette once and produce a `RecordingStats`."""
    header, entries = load_recording(path)
    tokens_in = 0
    tokens_out = 0
    cost = 0.0
    tool_calls: dict[str, int] = {}
    for entry in entries:
        response: dict[str, Any] = entry["response"]
        usage = response.get("usage") or {}
        tokens_in += int(usage.get("input_tokens", 0))
        tokens_out += int(usage.get("output_tokens", 0))
        cost += float(response.get("cost_usd", 0.0))
        for tc in response.get("tool_calls", []) or []:
            tool_calls[tc["name"]] = tool_calls.get(tc["name"], 0) + 1
    return RecordingStats(
        call_count=len(entries),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        tool_call_names=tool_calls,
        redactions=list(header.get("redactions", [])),
        format_version=int(header.get("format_version", 1)),
    )


__all__ = ["RecordingStats", "analyze_recording"]
