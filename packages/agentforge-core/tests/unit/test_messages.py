"""Unit tests for the message / response value types."""

from __future__ import annotations

import pytest
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
    ToolSpec,
)
from pydantic import ValidationError

# ---- Message ----


def test_message_basic_construction() -> None:
    m = Message(role="user", content="hi")
    assert m.role == "user"
    assert m.content == "hi"
    assert m.name is None
    assert m.tool_call_id is None


def test_message_is_frozen() -> None:
    m = Message(role="user", content="hi")
    with pytest.raises(ValidationError):
        m.role = "system"  # type: ignore[misc]


def test_message_rejects_invalid_role() -> None:
    with pytest.raises(ValidationError):
        Message(role="captain", content="hi")  # type: ignore[arg-type]


@pytest.mark.parametrize("role", ["system", "user", "assistant", "tool"])
def test_message_accepts_each_valid_role(role: str) -> None:
    Message(role=role, content="ok")  # type: ignore[arg-type]


# ---- ToolCall ----


def test_tool_call_basic() -> None:
    tc = ToolCall(id="t-1", name="search", arguments={"q": "hi"})
    assert tc.id == "t-1"
    assert tc.arguments == {"q": "hi"}


def test_tool_call_arguments_default_empty() -> None:
    tc = ToolCall(id="t-1", name="ping")
    assert tc.arguments == {}


def test_tool_call_is_frozen() -> None:
    tc = ToolCall(id="t-1", name="x", arguments={})
    with pytest.raises(ValidationError):
        tc.id = "t-2"  # type: ignore[misc]


# ---- ToolSpec ----


def test_tool_spec_basic() -> None:
    spec = ToolSpec(
        name="search",
        description="Web search",
        schema={"type": "object", "properties": {"q": {"type": "string"}}},
    )
    assert spec.name == "search"
    assert spec.schema_["type"] == "object"


def test_tool_spec_schema_alias_round_trip() -> None:
    """The Python attribute is `schema_` but the JSON key is `schema`."""
    spec = ToolSpec(name="x", description="y", schema={"type": "object"})
    payload = spec.model_dump(by_alias=True)
    assert "schema" in payload
    assert "schema_" not in payload


# ---- TokenUsage ----


def test_token_usage_total() -> None:
    u = TokenUsage(input_tokens=100, output_tokens=50)
    assert u.total == 150


def test_token_usage_total_excludes_cache_and_thinking() -> None:
    u = TokenUsage(
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=100,
        cache_write_tokens=20,
        thinking_tokens=1000,
    )
    assert u.total == 15  # cache and thinking are accounting metadata


def test_token_usage_negatives_rejected() -> None:
    with pytest.raises(ValidationError):
        TokenUsage(input_tokens=-1, output_tokens=0)


# ---- LLMResponse ----


def _usage(i: int = 1, o: int = 1) -> TokenUsage:
    return TokenUsage(input_tokens=i, output_tokens=o)


def test_llm_response_basic() -> None:
    r = LLMResponse(
        content="ok",
        stop_reason="end_turn",
        usage=_usage(),
        cost_usd=0.001,
        model="m",
        provider="p",
    )
    assert r.tool_calls == ()
    assert r.cost_usd == pytest.approx(0.001)


def test_llm_response_is_frozen() -> None:
    r = LLMResponse(
        content="x",
        stop_reason="end_turn",
        usage=_usage(),
        cost_usd=0.0,
        model="m",
        provider="p",
    )
    with pytest.raises(ValidationError):
        r.content = "y"  # type: ignore[misc]


def test_llm_response_rejects_negative_cost() -> None:
    with pytest.raises(ValidationError):
        LLMResponse(
            content="x",
            stop_reason="end_turn",
            usage=_usage(),
            cost_usd=-0.01,
            model="m",
            provider="p",
        )


@pytest.mark.parametrize(
    "stop",
    ["end_turn", "tool_use", "max_tokens", "stop_sequence", "other"],
)
def test_llm_response_accepts_every_stop_reason(stop: str) -> None:
    LLMResponse(
        content="x",
        stop_reason=stop,  # type: ignore[arg-type]
        usage=_usage(),
        cost_usd=0.0,
        model="m",
        provider="p",
    )
