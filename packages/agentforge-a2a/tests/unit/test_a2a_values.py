"""Unit tests for A2A value models (feat-014)."""

from __future__ import annotations

import pytest
from agentforge_a2a import (
    A2AEndpointConfig,
    A2AExposeConfig,
    A2APeerConfig,
    A2AResponse,
)
from pydantic import ValidationError


def test_a2a_response_minimal() -> None:
    r = A2AResponse(output="ok", run_id="r1")
    assert r.cost_usd == 0.0
    assert r.findings == ()
    assert r.parent_run_id is None


def test_a2a_response_is_frozen() -> None:
    r = A2AResponse(output="ok", run_id="r1")
    with pytest.raises(ValidationError):
        r.run_id = "r2"  # type: ignore[misc]


def test_a2a_response_negative_cost_rejected() -> None:
    with pytest.raises(ValidationError):
        A2AResponse(output="ok", run_id="r1", cost_usd=-0.01)


def test_a2a_peer_config_requires_name_and_url() -> None:
    with pytest.raises(ValidationError):
        A2APeerConfig(name="", url="https://x")
    with pytest.raises(ValidationError):
        A2APeerConfig(name="x", url="")


def test_a2a_peer_config_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        A2APeerConfig(name="n", url="u", extra=1)  # type: ignore[call-arg]


def test_a2a_expose_config_defaults() -> None:
    cfg = A2AExposeConfig()
    assert cfg.enabled is True
    assert cfg.port == 8080
    assert cfg.endpoints == []


def test_a2a_endpoint_config_round_trip() -> None:
    e = A2AEndpointConfig(name="review-pr", description="d", accepts={"pr_url": "string"})
    blob = e.model_dump_json()
    restored = A2AEndpointConfig.model_validate_json(blob)
    assert restored == e
