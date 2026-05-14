"""Unit tests for `_SentenceWindowBuffer` (feat-020 v0.3 polish)."""

from __future__ import annotations

from agentforge_chat._window import _SOFT_MAX_CHARS, _SentenceWindowBuffer


def test_push_returns_empty_until_terminator() -> None:
    buf = _SentenceWindowBuffer()
    assert buf.push("hello ") == []
    assert buf.push("world") == []
    # Terminator with no trailing whitespace stays buffered too —
    # we wait for the punctuation-then-whitespace pattern.
    assert buf.push(".") == []
    # Now a trailing space closes the sentence.
    assert buf.push(" ") == ["hello world."]


def test_push_extracts_multiple_sentences() -> None:
    buf = _SentenceWindowBuffer()
    sentences = buf.push("First sentence. Second one! Third? ")
    assert sentences == ["First sentence.", "Second one!", "Third?"]


def test_push_treats_newline_as_boundary() -> None:
    buf = _SentenceWindowBuffer()
    sentences = buf.push("Line one\nLine two\n")
    assert sentences == ["Line one", "Line two"]


def test_push_keeps_partial_after_terminator() -> None:
    buf = _SentenceWindowBuffer()
    sentences = buf.push("Done. Continuing")
    assert sentences == ["Done."]
    # The partial stays in the buffer; flushing returns it.
    assert buf.flush() == "Continuing"


def test_push_hard_caps_long_unpunctuated_text() -> None:
    """A paragraph without punctuation must still emit before the
    buffer grows unbounded — the soft cap fires at
    `_SOFT_MAX_CHARS`."""
    buf = _SentenceWindowBuffer()
    long_text = "a" * (_SOFT_MAX_CHARS + 50)
    completed = buf.push(long_text)
    assert len(completed) == 1
    assert len(completed[0]) == _SOFT_MAX_CHARS


def test_flush_empties_the_buffer() -> None:
    buf = _SentenceWindowBuffer()
    buf.push("Partial without terminator")
    assert buf.flush() == "Partial without terminator"
    assert buf.flush() == ""


def test_push_empty_text_is_noop() -> None:
    buf = _SentenceWindowBuffer()
    assert buf.push("") == []
    assert buf.flush() == ""
