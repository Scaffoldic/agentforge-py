"""Unit tests for `Principal` (feat-014)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from agentforge_core.values.auth import Principal


def test_principal_minimal() -> None:
    p = Principal(id="u1")
    assert p.id == "u1"
    assert p.metadata == {}


def test_principal_is_frozen() -> None:
    p = Principal(id="u1")
    with pytest.raises(FrozenInstanceError):
        p.id = "u2"  # type: ignore[misc]


def test_principal_equality() -> None:
    a = Principal(id="u1", metadata={"role": "admin"})
    b = Principal(id="u1", metadata={"role": "admin"})
    assert a == b
