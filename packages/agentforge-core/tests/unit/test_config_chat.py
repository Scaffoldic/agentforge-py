"""Unit tests for `modules.chat:` schema (feat-020)."""

from __future__ import annotations

import pytest
from agentforge_core.config.schema import (
    AgentForgeConfig,
    ChatConfig,
    ChatSessionConfig,
    ModulesConfig,
)
from pydantic import ValidationError


def test_chat_config_defaults() -> None:
    cfg = ChatConfig()
    assert cfg.history is None
    assert cfg.truncation is None
    assert cfg.session.idempotency_window_s == 60.0
    assert cfg.session.concurrency == "queue"
    assert cfg.session.safety_mode == "buffer-then-stream"


def test_modules_chat_defaults_to_none() -> None:
    assert ModulesConfig().chat is None


def test_session_rejects_negative_budget() -> None:
    with pytest.raises(ValidationError):
        ChatSessionConfig(per_turn_budget_usd=-0.01)


def test_session_rejects_invalid_concurrency() -> None:
    with pytest.raises(ValidationError):
        ChatSessionConfig(concurrency="discard")  # type: ignore[arg-type]


def test_session_rejects_invalid_safety_mode() -> None:
    with pytest.raises(ValidationError):
        ChatSessionConfig(safety_mode="dropout")  # type: ignore[arg-type]


def test_chat_config_extra_keys_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatConfig(unknown_field=1)  # type: ignore[call-arg]


def test_full_config_round_trip() -> None:
    raw = {
        "modules": {
            "chat": {
                "history": {"driver": "sqlite", "config": {"path": "./chat.db"}},
                "truncation": {
                    "strategy": "sliding_window",
                    "config": {"max_turns": 100},
                },
                "session": {
                    "per_turn_budget_usd": 0.5,
                    "per_session_budget_usd": 5.0,
                    "idempotency_window_s": 30,
                    "concurrency": "reject",
                },
            }
        }
    }
    cfg = AgentForgeConfig.model_validate(raw)
    assert cfg.modules.chat is not None
    assert cfg.modules.chat.history is not None
    assert cfg.modules.chat.history.driver == "sqlite"
    assert cfg.modules.chat.truncation is not None
    assert cfg.modules.chat.truncation.strategy == "sliding_window"
    assert cfg.modules.chat.session.per_turn_budget_usd == 0.5
    assert cfg.modules.chat.session.concurrency == "reject"
