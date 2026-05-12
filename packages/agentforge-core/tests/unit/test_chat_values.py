"""Unit tests for chat value models (feat-020)."""

from __future__ import annotations

import pytest
from agentforge_core.values.chat import ChatChunk, ChatResponse, ChatTurn, SessionInfo
from pydantic import ValidationError


def test_chat_turn_minimal() -> None:
    t = ChatTurn(id="01HX", session_id="s1", role="user", content="hi")
    assert t.tokens_in == 0
    assert t.cost_usd == 0.0
    assert t.run_id is None


def test_chat_turn_is_frozen() -> None:
    t = ChatTurn(id="01HX", session_id="s1", role="user", content="hi")
    with pytest.raises(ValidationError):
        t.content = "boom"  # type: ignore[misc]


def test_chat_turn_role_closed_enum() -> None:
    with pytest.raises(ValidationError):
        ChatTurn(id="01HX", session_id="s1", role="root", content="hi")  # type: ignore[arg-type]


def test_chat_chunk_kind_closed_enum() -> None:
    ChatChunk(kind="text", turn_id="t1", content="hello")
    with pytest.raises(ValidationError):
        ChatChunk(kind="snore", turn_id="t1")  # type: ignore[arg-type]


def test_session_info_defaults() -> None:
    info = SessionInfo(id="s1")
    assert info.owner is None
    assert info.turn_count == 0
    assert info.total_cost_usd == 0.0


def test_chat_response_round_trip() -> None:
    r = ChatResponse(content="ok", turn_id="t", run_id="r")
    blob = r.model_dump_json()
    restored = ChatResponse.model_validate_json(blob)
    assert restored == r
