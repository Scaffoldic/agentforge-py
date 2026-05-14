"""Unit tests for `LiteLLMClient`."""

from __future__ import annotations

import pytest
from agentforge_core.values.messages import Message, ToolSpec
from agentforge_litellm import LiteLLMClient
from agentforge_litellm._inmem_runner import FakeLiteLLMRunner


def _user(text: str) -> Message:
    return Message(role="user", content=text)


def test_constructor_rejects_empty_model(fake_runner: FakeLiteLLMRunner) -> None:
    with pytest.raises(ValueError, match="model_id"):
        LiteLLMClient(runner=fake_runner, model_id="")


def test_constructor_rejects_zero_timeout(fake_runner: FakeLiteLLMRunner) -> None:
    with pytest.raises(ValueError, match="timeout"):
        LiteLLMClient(runner=fake_runner, model_id="x", timeout_seconds=0)


def test_capabilities_declares_only_tools(client: LiteLLMClient) -> None:
    assert client.capabilities() == {"tools"}
    assert not client.supports("caching")
    assert not client.supports("streaming")


@pytest.mark.asyncio
async def test_call_hoists_system_prompt(
    client: LiteLLMClient,
    fake_runner: FakeLiteLLMRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                },
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
            "_hidden_params": {"response_cost": 0.0012},
        },
    )
    resp = await client.call(system="be brief", messages=[_user("hi")])
    assert fake_runner.calls[0].messages[0] == {"role": "system", "content": "be brief"}
    assert resp.content == "ok"
    assert resp.cost_usd == pytest.approx(0.0012)
    assert resp.provider == "litellm"


@pytest.mark.asyncio
async def test_call_passes_tool_specs_in_openai_shape(
    client: LiteLLMClient,
    fake_runner: FakeLiteLLMRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": "stop",
                },
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        },
    )
    await client.call(
        system="",
        messages=[_user("hi")],
        tools=[ToolSpec(name="t", description="d", schema={"type": "object"})],
    )
    tools = fake_runner.calls[0].tools
    assert tools is not None
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "t"


@pytest.mark.asyncio
async def test_call_normalises_tool_calls(
    client: LiteLLMClient,
    fake_runner: FakeLiteLLMRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "t1",
                                "function": {"name": "calc", "arguments": '{"a":2}'},
                            },
                        ],
                    },
                    "finish_reason": "tool_calls",
                },
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )
    resp = await client.call(system="", messages=[_user("compute")])
    assert resp.stop_reason == "tool_use"
    assert resp.tool_calls[0].name == "calc"
    assert resp.tool_calls[0].arguments == {"a": 2}


@pytest.mark.asyncio
async def test_call_malformed_tool_args_yield_empty_dict(
    client: LiteLLMClient,
    fake_runner: FakeLiteLLMRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {"id": "t1", "function": {"name": "calc", "arguments": "not-json"}},
                        ],
                    },
                    "finish_reason": "tool_calls",
                },
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )
    resp = await client.call(system="", messages=[_user("hi")])
    assert resp.tool_calls[0].arguments == {}


@pytest.mark.asyncio
async def test_call_missing_response_cost_yields_zero(
    client: LiteLLMClient,
    fake_runner: FakeLiteLLMRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "x",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "x"},
                    "finish_reason": "stop",
                },
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )
    resp = await client.call(system="", messages=[_user("hi")])
    assert resp.cost_usd == 0.0


@pytest.mark.asyncio
async def test_call_negative_response_cost_clamped_to_zero(
    client: LiteLLMClient,
    fake_runner: FakeLiteLLMRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "x",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "x"},
                    "finish_reason": "stop",
                },
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "_hidden_params": {"response_cost": -0.0001},
        },
    )
    resp = await client.call(system="", messages=[_user("hi")])
    assert resp.cost_usd == 0.0


@pytest.mark.asyncio
async def test_tool_role_messages_encode_with_tool_call_id(
    client: LiteLLMClient,
    fake_runner: FakeLiteLLMRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "x",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": "stop",
                },
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        },
    )
    await client.call(
        system="",
        messages=[Message(role="tool", content="42", tool_call_id="abc")],
    )
    sent = fake_runner.calls[0].messages[0]
    assert sent == {"role": "tool", "tool_call_id": "abc", "content": "42"}


@pytest.mark.asyncio
async def test_extra_kwargs_propagate_to_runner(fake_runner: FakeLiteLLMRunner) -> None:
    fake_runner.set_response(
        {
            "model": "x",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": "stop",
                },
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        },
    )
    c = LiteLLMClient(
        runner=fake_runner,
        model_id="x",
        extra={"temperature": 0.2, "metadata": {"trace_id": "t1"}},
    )
    await c.call(system="", messages=[_user("hi")])
    extra = fake_runner.calls[0].extra
    assert extra["temperature"] == 0.2
    assert extra["metadata"] == {"trace_id": "t1"}


@pytest.mark.asyncio
async def test_close_propagates(
    client: LiteLLMClient,
    fake_runner: FakeLiteLLMRunner,
) -> None:
    await client.close()
    assert fake_runner.closed
