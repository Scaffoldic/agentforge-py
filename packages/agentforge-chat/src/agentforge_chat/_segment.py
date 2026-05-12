"""Sentence segmenter for the buffer-then-stream path (feat-020).

v0.2 ships `ChatSession.stream()` in the spec's
`safety_mode: "buffer-then-stream"` semantics: the agent runs to
completion, then the assistant turn is sliced into sentence-ish
chunks for the wire format. Real per-token streaming follows in a
later release without changing this surface.
"""

from __future__ import annotations

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_MAX_CHUNK_CHARS = 200
"""Soft cap so a single uninterrupted paragraph still emits as
multiple chunks."""


def segment_for_stream(text: str) -> list[str]:
    """Split ``text`` into wire-format-friendly chunks.

    Prefers sentence boundaries (``.!?`` followed by whitespace);
    falls back to paragraph boundaries; falls back to a hard
    `_MAX_CHUNK_CHARS` cap.
    """
    if not text:
        return []
    parts = [p for p in _SENTENCE_BOUNDARY.split(text) if p]
    out: list[str] = []
    for part in parts:
        out.extend(_split_long(part))
    return out


def _split_long(text: str) -> list[str]:
    if len(text) <= _MAX_CHUNK_CHARS:
        return [text]
    pieces: list[str] = []
    cursor = 0
    while cursor < len(text):
        end = min(cursor + _MAX_CHUNK_CHARS, len(text))
        pieces.append(text[cursor:end])
        cursor = end
    return pieces
