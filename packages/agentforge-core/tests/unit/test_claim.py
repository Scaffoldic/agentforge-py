"""Unit tests for `Claim`."""

from __future__ import annotations

import pytest
from agentforge_core.values.claim import Claim
from pydantic import ValidationError


def _make(**overrides: object) -> Claim:
    base: dict[str, object] = {
        "run_id": "r1",
        "project": "proj",
        "agent": "ag",
        "category": "finding",
        "payload": {"x": 1},
    }
    base.update(overrides)
    return Claim(**base)  # type: ignore[arg-type]


def test_claim_basic() -> None:
    c = _make()
    assert c.run_id == "r1"
    assert c.project == "proj"
    assert c.agent == "ag"
    assert c.category == "finding"
    assert c.payload == {"x": 1}
    assert c.supersedes is None


def test_claim_id_default_is_ulid() -> None:
    c = _make()
    assert isinstance(c.id, str)
    # ULID Crockford-Base32: 26 chars
    assert len(c.id) == 26


def test_claim_distinct_ids() -> None:
    a = _make()
    b = _make()
    assert a.id != b.id


def test_claim_is_frozen() -> None:
    c = _make()
    with pytest.raises(ValidationError):
        c.payload = {"y": 2}  # type: ignore[misc]


def test_claim_supersedes_link() -> None:
    older = _make()
    newer = _make(supersedes=older.id)
    assert newer.supersedes == older.id


def test_claim_explicit_id_preserved() -> None:
    c = _make(id="01HX-MANUAL")
    assert c.id == "01HX-MANUAL"


def test_claim_round_trip_json() -> None:
    c = _make()
    payload = c.model_dump_json()
    restored = Claim.model_validate_json(payload)
    assert restored == c
