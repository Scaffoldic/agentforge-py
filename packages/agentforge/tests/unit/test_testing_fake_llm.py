"""Unit tests for `FakeLLMClient`."""

from __future__ import annotations

import pytest
from agentforge._testing import FakeLLMClient
from agentforge._testing.fake_llm import echo_response
from agentforge_core.values.messages import LLMResponse, Message, TokenUsage


def _resp(content: str = "ok") -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=1, output_tokens=1),
        cost_usd=0.0,
        model="fake",
        provider="fake",
    )


@pytest.mark.asyncio
async def test_returns_scripted_responses_in_order() -> None:
    fake = FakeLLMClient(responses=[_resp("a"), _resp("b")])
    a = await fake.call("sys", [Message(role="user", content="x")])
    b = await fake.call("sys", [Message(role="user", content="y")])
    assert a.content == "a"
    assert b.content == "b"
    assert fake.call_count == 2


@pytest.mark.asyncio
async def test_exhaustion_raises() -> None:
    fake = FakeLLMClient(responses=[_resp("only")])
    await fake.call("sys", [Message(role="user", content="x")])
    with pytest.raises(RuntimeError, match="exhausted"):
        await fake.call("sys", [Message(role="user", content="y")])


@pytest.mark.asyncio
async def test_callable_response_spec() -> None:
    def builder(*, system, messages, tools=None) -> LLMResponse:
        return _resp(content=f"echo:{messages[-1].content}")

    fake = FakeLLMClient(responses=[builder])
    response = await fake.call("sys", [Message(role="user", content="hello")])
    assert response.content == "echo:hello"


@pytest.mark.asyncio
async def test_captures_call_arguments() -> None:
    fake = FakeLLMClient(responses=[_resp(), _resp()])
    msgs1 = [Message(role="user", content="first")]
    msgs2 = [Message(role="user", content="second")]
    await fake.call("sys-a", msgs1)
    await fake.call("sys-b", msgs2)
    captured = fake.captured
    assert len(captured) == 2
    assert captured[0][0] == "sys-a"
    assert captured[0][1] == msgs1
    assert captured[1][0] == "sys-b"


@pytest.mark.asyncio
async def test_close_marks_closed_and_subsequent_calls_raise() -> None:
    fake = FakeLLMClient(responses=[_resp()])
    await fake.close()
    with pytest.raises(RuntimeError, match="close"):
        await fake.call("sys", [])


def test_capabilities_default_empty() -> None:
    assert FakeLLMClient().capabilities() == set()


def test_capabilities_round_trip() -> None:
    fake = FakeLLMClient(capabilities={"caching", "thinking"})
    assert fake.capabilities() == {"caching", "thinking"}
    assert fake.supports("caching") is True
    assert fake.supports("streaming") is False


def test_echo_response_defaults() -> None:
    r = echo_response()
    assert r.content == "ok"
    assert r.stop_reason == "end_turn"
    assert r.usage.input_tokens == 1


def test_echo_response_overrides() -> None:
    r = echo_response(content="custom", input_tokens=42, cost_usd=0.05)
    assert r.content == "custom"
    assert r.usage.input_tokens == 42
    assert r.cost_usd == pytest.approx(0.05)
