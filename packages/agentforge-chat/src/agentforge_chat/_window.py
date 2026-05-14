"""Sentence-window buffer for the streaming output-guardrail path
(feat-020 v0.3 polish).

When `ChatSession.safety_mode == "sentence-window"`, streamed text
tokens accumulate in a `_SentenceWindowBuffer`. Each `push(text)` call
returns the completed sentences ready to validate (terminator
followed by whitespace, OR newline, OR 200-char hard cap so a
paragraph without punctuation still flushes). The buffer's
`flush()` returns whatever residual remains so callers can pipe
the partial through the guardrail one last time at end-of-stream.

Boundary heuristic mirrors :mod:`agentforge_chat._segment` so the
streaming and buffer-then-stream paths produce comparable chunk
shapes. Multi-language sentence segmentation is out of scope for
v0.3; the regex is English-centric.
"""

from __future__ import annotations

import re

_SOFT_MAX_CHARS = 200
"""Soft cap so an unpunctuated paragraph still emits as chunks."""

_BOUNDARY_RE = re.compile(r"[.!?]\s+|\n+")


class _SentenceWindowBuffer:
    """Accumulates streamed tokens; releases completed sentences.

    Not thread-safe — `ChatSession._stream_per_token` already
    serialises per-session via a lock, so each buffer instance is
    single-writer / single-reader.
    """

    def __init__(self) -> None:
        self._buf = ""

    def push(self, text: str) -> list[str]:
        """Append `text` to the buffer; return any completed sentences.

        A sentence is "completed" when:
        - a `.!?` is followed by whitespace, OR
        - a newline appears, OR
        - the buffer length exceeds `_SOFT_MAX_CHARS`.

        Remaining partial text stays buffered until the next push
        or a `flush()`.
        """
        if not text:
            return []
        self._buf += text
        completed: list[str] = []
        while True:
            cut = self._find_cut()
            if cut is None:
                break
            sentence = self._buf[:cut].rstrip()
            if sentence:
                completed.append(sentence)
            self._buf = self._buf[cut:].lstrip()
        return completed

    def flush(self) -> str:
        """Return the residual buffer contents + reset internal state.

        Callers run this through their per-sentence pipeline one
        last time so end-of-stream text isn't dropped on the floor.
        Returns an empty string when the buffer is already empty.
        """
        residual, self._buf = self._buf, ""
        return residual

    def _find_cut(self) -> int | None:
        """Return the byte index at which to slice off a completed
        sentence, or `None` if nothing is ready yet.

        Priority: punctuation/newline boundary first; hard-cap
        fallback at `_SOFT_MAX_CHARS`.
        """
        match = _BOUNDARY_RE.search(self._buf)
        if match is not None:
            return match.end()
        if len(self._buf) >= _SOFT_MAX_CHARS:
            return _SOFT_MAX_CHARS
        return None
