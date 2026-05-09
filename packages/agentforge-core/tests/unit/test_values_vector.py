"""Unit tests for the `VectorItem` and `VectorMatch` value types."""

from __future__ import annotations

import pytest
from agentforge_core.values.vector import VectorItem, VectorMatch
from pydantic import ValidationError

# ---- VectorItem ----


def test_vector_item_basic() -> None:
    item = VectorItem(id="x", vector=(1.0, 0.0, 0.0), text="hello")
    assert item.id == "x"
    assert item.vector == (1.0, 0.0, 0.0)
    assert item.text == "hello"
    assert item.metadata == {}


def test_vector_item_rejects_empty_id() -> None:
    with pytest.raises(ValidationError):
        VectorItem(id="", vector=(1.0,), text="x")


def test_vector_item_is_frozen() -> None:
    item = VectorItem(id="x", vector=(0.5,), text="x")
    with pytest.raises(ValidationError):
        item.text = "mutated"  # type: ignore[misc]


def test_vector_item_metadata_defaults_to_empty_dict() -> None:
    item = VectorItem(id="x", vector=(1.0,), text="x")
    assert item.metadata == {}


def test_vector_item_metadata_accepts_arbitrary_payload() -> None:
    item = VectorItem(
        id="x",
        vector=(1.0,),
        text="x",
        metadata={"category": "doc", "year": 2024, "tags": ["a", "b"]},
    )
    assert item.metadata["category"] == "doc"
    assert item.metadata["tags"] == ["a", "b"]


def test_vector_item_vector_must_be_a_tuple() -> None:
    """Strict-mode pydantic rejects lists where tuples are declared.
    Forces callers to think about immutability — vectors should be
    `tuple[float, ...]`, not mutable lists that might be aliased
    elsewhere."""
    with pytest.raises(ValidationError):
        VectorItem(id="x", vector=[1.0, 2.0, 3.0], text="x")  # type: ignore[arg-type]


# ---- VectorMatch ----


def test_vector_match_basic() -> None:
    m = VectorMatch(id="x", text="hello", score=0.85)
    assert m.id == "x"
    assert m.score == 0.85


def test_vector_match_rejects_score_above_one() -> None:
    with pytest.raises(ValidationError):
        VectorMatch(id="x", text="hello", score=1.5)


def test_vector_match_rejects_negative_score() -> None:
    with pytest.raises(ValidationError):
        VectorMatch(id="x", text="hello", score=-0.1)


def test_vector_match_score_at_zero_and_one_allowed() -> None:
    """Boundary values must be allowed — orthogonal (0) and identical
    (1) are both legitimate scores under the contract."""
    VectorMatch(id="x", text="x", score=0.0)
    VectorMatch(id="x", text="x", score=1.0)


def test_vector_match_is_frozen() -> None:
    m = VectorMatch(id="x", text="x", score=0.5)
    with pytest.raises(ValidationError):
        m.score = 0.9  # type: ignore[misc]
