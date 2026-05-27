"""Unit tests for `OpenAIClient`."""

from __future__ import annotations

import json

import pytest
from agentforge_core.values.messages import Message, ToolCall, ToolSpec
from agentforge_openai import OpenAIClient
from agentforge_openai._inmem_runner import FakeOpenAIRunner
from agentforge_openai._pricing import chat_cost_usd


def _user(text: str) -> Message:
    return Message(role="user", content=text)


def test_constructor_rejects_empty_model(fake_runner: FakeOpenAIRunner) -> None:
    with pytest.raises(ValueError, match="model_id"):
        OpenAIClient(runner=fake_runner, model_id="")


def test_constructor_rejects_zero_timeout(fake_runner: FakeOpenAIRunner) -> None:
    with pytest.raises(ValueError, match="timeout"):
        OpenAIClient(runner=fake_runner, model_id="gpt-4o", timeout_seconds=0)


def test_capabilities_gpt4o_has_vision(fake_runner: FakeOpenAIRunner) -> None:
    c = OpenAIClient(runner=fake_runner, model_id="gpt-4o")
    caps = c.capabilities()
    assert "tools" in caps
    assert "json_mode" in caps
    assert "streaming" in caps
    assert "vision" in caps


def test_capabilities_o3_no_vision(fake_runner: FakeOpenAIRunner) -> None:
    c = OpenAIClient(runner=fake_runner, model_id="o3")
    assert "vision" not in c.capabilities()


def test_dated_model_strips_to_canonical_for_vision_check(
    fake_runner: FakeOpenAIRunner,
) -> None:
    c = OpenAIClient(runner=fake_runner, model_id="gpt-4o-2026-03-01")
    assert "vision" in c.capabilities()


@pytest.mark.asyncio
async def test_call_hoists_system_prompt_as_first_message(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_chat_response(
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
        },
    )

    resp = await client.call(system="be brief", messages=[_user("hi")])

    msgs = fake_runner.chat_calls[0].messages
    assert msgs[0] == {"role": "system", "content": "be brief"}
    assert msgs[1]["role"] == "user"
    assert resp.content == "ok"
    assert resp.usage.input_tokens == 4
    assert resp.usage.output_tokens == 1
    assert resp.provider == "openai"


@pytest.mark.asyncio
async def test_call_omits_system_when_empty(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_chat_response(
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
    await client.call(system="", messages=[_user("hi")])
    msgs = fake_runner.chat_calls[0].messages
    assert msgs[0]["role"] == "user"


@pytest.mark.asyncio
async def test_call_normalises_tool_calls(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_chat_response(
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
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "calc",
                                    "arguments": '{"a": 1}',
                                },
                            },
                        ],
                    },
                    "finish_reason": "tool_calls",
                },
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        },
    )
    resp = await client.call(
        system="",
        messages=[_user("compute")],
        tools=[ToolSpec(name="calc", description="adds", schema={"type": "object"})],
    )
    assert resp.stop_reason == "tool_use"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "calc"
    assert resp.tool_calls[0].arguments == {"a": 1}


@pytest.mark.asyncio
async def test_call_handles_malformed_tool_arguments(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_chat_response(
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
                                "id": "call_2",
                                "type": "function",
                                "function": {"name": "calc", "arguments": "not json"},
                            },
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
async def test_call_flattens_content_part_lists(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_chat_response(
        {
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "hel"},
                            {"type": "text", "text": "lo"},
                        ],
                    },
                    "finish_reason": "stop",
                },
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )
    resp = await client.call(system="", messages=[_user("hi")])
    assert resp.content == "hello"


@pytest.mark.asyncio
async def test_tool_role_messages_pass_with_tool_call_id(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_chat_response(
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
        messages=[Message(role="tool", content="42", tool_call_id="call_1")],
    )
    sent = fake_runner.chat_calls[0].messages[0]
    assert sent["role"] == "tool"
    assert sent["tool_call_id"] == "call_1"
    assert sent["content"] == "42"


@pytest.mark.asyncio
async def test_assistant_turn_with_tool_calls_emits_openai_tool_calls(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    """bug-009: an assistant Message carrying framework tool_calls must
    serialise to OpenAI's `tool_calls` array with JSON-encoded arguments,
    so the subsequent role="tool" message pairs cleanly via tool_call_id."""
    fake_runner.set_chat_response(
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
        messages=[
            Message(
                role="assistant",
                content="calling",
                tool_calls=(ToolCall(id="call_1", name="search", arguments={"q": "x"}),),
            ),
            Message(role="tool", content="result", tool_call_id="call_1"),
        ],
    )
    sent = fake_runner.chat_calls[0].messages[0]
    assert sent["role"] == "assistant"
    assert sent["tool_calls"][0]["id"] == "call_1"
    assert sent["tool_calls"][0]["type"] == "function"
    assert sent["tool_calls"][0]["function"]["name"] == "search"
    assert json.loads(sent["tool_calls"][0]["function"]["arguments"]) == {"q": "x"}


@pytest.mark.asyncio
async def test_call_finish_reason_length_maps_to_max_tokens(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_chat_response(
        {
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "..."},
                    "finish_reason": "length",
                },
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 100, "total_tokens": 101},
        },
    )
    resp = await client.call(system="", messages=[_user("hi")])
    assert resp.stop_reason == "max_tokens"


@pytest.mark.asyncio
async def test_call_unknown_finish_reason_maps_to_other(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_chat_response(
        {
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "x"},
                    "finish_reason": "function_invocation_aborted",
                },
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )
    resp = await client.call(system="", messages=[_user("hi")])
    assert resp.stop_reason == "other"


@pytest.mark.asyncio
async def test_json_mode_sets_response_format(
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_chat_response(
        {
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "{}"},
                    "finish_reason": "stop",
                },
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )
    c = OpenAIClient(runner=fake_runner, model_id="gpt-4o-mini", json_mode=True)
    await c.call(system="", messages=[_user("hi")])
    extra = fake_runner.chat_calls[0].extra
    assert extra["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_call_passes_tool_specs(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_chat_response(
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
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
    await client.call(
        system="",
        messages=[_user("hi")],
        tools=[ToolSpec(name="t", description="d", schema=schema)],
    )
    tools_arg = fake_runner.chat_calls[0].tools
    assert tools_arg is not None
    assert tools_arg[0]["type"] == "function"
    assert tools_arg[0]["function"]["name"] == "t"
    assert tools_arg[0]["function"]["parameters"] == schema


# ----------------------------------------------------------------------
# Streaming
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_concatenates_text_deltas(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_stream_chunks(
        [
            {
                "choices": [
                    {"index": 0, "delta": {"content": "hel"}, "finish_reason": None},
                ],
            },
            {
                "choices": [
                    {"index": 0, "delta": {"content": "lo"}, "finish_reason": None},
                ],
            },
            {
                "choices": [
                    {"index": 0, "delta": {}, "finish_reason": "stop"},
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        ],
    )
    chunks = [c async for c in client.stream(system="", messages=[_user("hi")])]
    text = "".join(c.delta for c in chunks if c.kind == "text")
    assert text == "hello"
    stop = chunks[-1]
    assert stop.kind == "stop"
    assert stop.stop_reason == "end_turn"
    assert stop.usage is not None
    assert stop.usage.input_tokens == 5


@pytest.mark.asyncio
async def test_stream_accumulates_tool_call_argument_deltas(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    fake_runner.set_stream_chunks(
        [
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "function": {"name": "calc", "arguments": '{"a":'},
                                },
                            ],
                        },
                        "finish_reason": None,
                    },
                ],
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": " 1}"},
                                },
                            ],
                        },
                        "finish_reason": None,
                    },
                ],
            },
            {
                "choices": [
                    {"index": 0, "delta": {}, "finish_reason": "tool_calls"},
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        ],
    )
    chunks = [c async for c in client.stream(system="", messages=[_user("hi")])]
    tool_chunks = [c for c in chunks if c.kind == "tool_call"]
    assert len(tool_chunks) == 1
    assert tool_chunks[0].tool_call is not None
    assert tool_chunks[0].tool_call.name == "calc"
    assert tool_chunks[0].tool_call.arguments == {"a": 1}


# ----------------------------------------------------------------------
# Pricing
# ----------------------------------------------------------------------


def test_pricing_known_model_is_nonzero() -> None:
    assert chat_cost_usd("gpt-4o-mini", input_tokens=1_000_000, output_tokens=0) > 0.0


def test_pricing_unknown_model_returns_zero() -> None:
    assert chat_cost_usd("internal-model", input_tokens=1000, output_tokens=1000) == 0.0


def test_pricing_strips_dated_suffix() -> None:
    base = chat_cost_usd("gpt-4o", input_tokens=1_000_000, output_tokens=0)
    dated = chat_cost_usd("gpt-4o-2026-03-01", input_tokens=1_000_000, output_tokens=0)
    assert base == dated


# ----------------------------------------------------------------------
# close
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_propagates(
    client: OpenAIClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    await client.close()
    assert fake_runner.closed
