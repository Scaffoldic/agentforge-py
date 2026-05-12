"""Smoke tests for the runner protocols (feat-014 chunk 2)."""

from __future__ import annotations

import pytest
from agentforge_a2a._runner import (
    A2AClientRunner,
    A2AServerRunner,
    _HTTPXClientRunner,
    _UvicornServerRunner,
)


def test_production_client_runner_raises_until_live_test_lands() -> None:
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        _HTTPXClientRunner()


def test_production_server_runner_raises_until_live_test_lands() -> None:
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        _UvicornServerRunner()


def test_protocols_are_importable() -> None:
    # Smoke: the Protocol classes are importable and runtime-checkable
    # only structurally — a typed `Any` check is enough.
    assert A2AClientRunner is not None
    assert A2AServerRunner is not None
