"""Unit tests for the private `_BM25Index` helper (feat-022)."""

from __future__ import annotations

import itertools

import pytest
from agentforge_core._bm25 import _BM25Index, _tokenise

# --- tokeniser ----------------------------------------------------


def test_tokenise_lowercases() -> None:
    assert _tokenise("Hello World") == ["hello", "world"]


def test_tokenise_drops_short_tokens() -> None:
    # Single-char tokens are filtered.
    assert _tokenise("I am here") == ["am", "here"]


def test_tokenise_splits_on_punctuation() -> None:
    assert _tokenise("foo, bar.baz!qux") == ["foo", "bar", "baz", "qux"]


def test_tokenise_empty() -> None:
    assert _tokenise("") == []
    assert _tokenise("   ") == []


# --- constructor validation ---------------------------------------


def test_constructor_validates_k1() -> None:
    with pytest.raises(ValueError, match="k1"):
        _BM25Index(k1=-0.1)


def test_constructor_validates_b() -> None:
    with pytest.raises(ValueError, match="b"):
        _BM25Index(b=1.5)
    with pytest.raises(ValueError, match="b"):
        _BM25Index(b=-0.1)


# --- score behaviour ----------------------------------------------


def test_empty_corpus_returns_empty() -> None:
    idx = _BM25Index()
    assert idx.score("anything", limit=5) == []


def test_empty_query_returns_empty() -> None:
    idx = _BM25Index()
    idx.add("a", "Paris is the capital of France")
    assert idx.score("", limit=5) == []


def test_limit_zero_raises() -> None:
    idx = _BM25Index()
    idx.add("a", "Paris")
    with pytest.raises(ValueError, match="limit"):
        idx.score("Paris", limit=0)


def test_single_doc_exact_match() -> None:
    idx = _BM25Index()
    idx.add("a", "Paris is the capital of France")
    results = idx.score("Paris", limit=5)
    assert len(results) == 1
    assert results[0][0] == "a"
    assert results[0][1] > 0.0


def test_top_hit_is_rarest_term() -> None:
    """The doc containing the rarest matching token wins."""
    idx = _BM25Index()
    idx.add("a", "Paris is the capital of France")
    idx.add("b", "Berlin is the capital of Germany")
    idx.add("c", "The Eiffel Tower is in Paris")
    # "Eiffel" appears only in c; "Paris" appears in a + c
    results = idx.score("Eiffel Tower Paris", limit=3)
    assert results[0][0] == "c"


def test_results_sorted_desc() -> None:
    idx = _BM25Index()
    idx.add("a", "Paris is the capital of France")
    idx.add("b", "Berlin is the capital of Germany")
    results = idx.score("capital", limit=5)
    for prev, nxt in itertools.pairwise(results):
        assert prev[1] >= nxt[1]


def test_limit_truncates() -> None:
    idx = _BM25Index()
    for i in range(5):
        idx.add(f"d{i}", "Paris is the capital of France")
    results = idx.score("Paris", limit=2)
    assert len(results) == 2


# --- delete -------------------------------------------------------


def test_delete_returns_existence() -> None:
    idx = _BM25Index()
    idx.add("a", "Paris")
    assert idx.delete("a") is True
    assert idx.delete("a") is False  # already gone


def test_delete_drops_from_score() -> None:
    idx = _BM25Index()
    idx.add("a", "Paris is the capital")
    idx.add("b", "Berlin is the capital")
    idx.delete("a")
    results = idx.score("Paris", limit=5)
    # a is gone; b doesn't mention Paris → empty
    assert results == []


def test_add_replaces_existing() -> None:
    idx = _BM25Index()
    idx.add("a", "Paris")
    idx.add("a", "Madrid")  # replaces
    paris = idx.score("Paris", limit=5)
    madrid = idx.score("Madrid", limit=5)
    assert paris == []
    assert madrid[0][0] == "a"


def test_len() -> None:
    idx = _BM25Index()
    assert len(idx) == 0
    idx.add("a", "x")
    assert len(idx) == 1
    idx.delete("a")
    assert len(idx) == 0


# --- knobs --------------------------------------------------------


def test_b_zero_disables_length_normalisation() -> None:
    """With b=0 the doc length should not affect ordering when TF is
    identical (the long doc no longer gets penalised)."""
    short_idx = _BM25Index(b=0.0)
    short_idx.add("short", "Paris")
    short_idx.add("long", "Paris " + "filler " * 100)
    results = short_idx.score("Paris", limit=5)
    # With b=0, both docs have identical TF-driven score (1 match each).
    # We just assert no length penalty kicked in (scores equal).
    assert results[0][1] == pytest.approx(results[1][1])
