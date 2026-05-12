"""Unit tests for `A2AConfig` (feat-014 chunk 5)."""

from __future__ import annotations

import pytest
from agentforge_a2a import A2ABridge, A2AConfig, A2AEndpointConfig, A2APeerConfig
from agentforge_a2a.values import A2AExposeConfig
from pydantic import ValidationError


def test_a2a_config_defaults() -> None:
    cfg = A2AConfig()
    assert cfg.peers == []
    assert cfg.expose is None


def test_a2a_config_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        A2AConfig(peers=[], unknown=1)  # type: ignore[call-arg]


def test_bearer_peer_validates() -> None:
    cfg = A2AConfig(
        peers=[
            A2APeerConfig(
                name="fact-checker",
                url="https://x/a2a",
                auth={"type": "bearer", "token": "t"},
            )
        ]
    )
    assert cfg.peers[0].name == "fact-checker"


def test_mtls_peer_validates() -> None:
    cfg = A2AConfig(
        peers=[
            A2APeerConfig(
                name="x",
                url="https://x/a2a",
                auth={"type": "mtls", "cert": "/p/cert.pem", "key": "/p/key.pem"},
            )
        ]
    )
    assert cfg.peers[0].auth["type"] == "mtls"


def test_expose_config_round_trip() -> None:
    cfg = A2AConfig(
        peers=[],
        expose=A2AExposeConfig(
            enabled=True,
            host="0.0.0.0",  # nosec B104
            port=9000,
            auth={"type": "bearer", "expected_tokens_env": "A2A_TOKENS"},
            endpoints=[A2AEndpointConfig(name="review-pr")],
        ),
    )
    blob = cfg.model_dump_json()
    restored = A2AConfig.model_validate_json(blob)
    assert restored == cfg


def test_bridge_declares_config_schema() -> None:
    """`A2ABridge.config_schema` must point at `A2AConfig` so
    feat-012's module-schema validator picks it up automatically
    on `agentforge config validate`."""
    assert A2ABridge.config_schema is A2AConfig
