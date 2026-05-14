"""Unit tests for `AnthropicClient`."""

from __future__ import annotations

import pytest
from agentforge_anthropic import AnthropicClient
from agentforge_anthropic._inmem_runner import FakeAnthropicRunner
from agentforge_anthropic._pricing import compute_cost_usd
from agentforge_core.production.exceptions import CapabilityNotSupported
from agentforge_core.values.messages import Message, ToolSpec


def _user(text: str) -> Message:
    return Message(role="user", content=text)


# ----------------------------------------------------------------------
# Construction
# ----------------------------------------------------------------------


def test_constructor_rejects_empty_model(fake_runner: FakeAnthropicRunner) -> None:
    with pytest.raises(ValueError, match="model_id"):
        AnthropicClient(runner=fake_runner, model_id="")


def test_constructor_rejects_zero_max_tokens(fake_runner: FakeAnthropicRunner) -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        AnthropicClient(runner=fake_runner, model_id="claude-sonnet-4-7", max_tokens=0)


def test_constructor_rejects_zero_timeout(fake_runner: FakeAnthropicRunner) -> None:
    with pytest.raises(ValueError, match="timeout"):
        AnthropicClient(runner=fake_runner, model_id="claude-sonnet-4-7", timeout_seconds=0.0)


def test_capabilities_declares_full_native_surface(client: AnthropicClient) -> None:
    assert client.capabilities() == {"tools", "json_mode", "caching", "thinking", "streaming"}
    assert client.supports("caching")
    assert client.supports("thinking")
    assert not client.supports("vision")


# ----------------------------------------------------------------------
# .call()
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_normalises_text_block_response(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_response(
        {
            "id": "msg_1",
            "model": "claude-sonnet-4-7",
            "content": [{"type": "text", "text": "hello"}],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 12,
                "output_tokens": 8,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        },
    )

    resp = await client.call(system="be brief", messages=[_user("hi")])

    assert resp.content == "hello"
    assert resp.tool_calls == ()
    assert resp.stop_reason == "end_turn"
    assert resp.usage.input_tokens == 12
    assert resp.usage.output_tokens == 8
    assert resp.provider == "anthropic"
    assert resp.cost_usd == compute_cost_usd(
        "claude-sonnet-4-7",
        input_tokens=12,
        output_tokens=8,
    )


@pytest.mark.asyncio
async def test_call_normalises_tool_use_blocks(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "claude-sonnet-4-7",
            "content": [
                {"type": "text", "text": "calling tool"},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "calculator",
                    "input": {"a": 1, "b": 2},
                },
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 5, "output_tokens": 4},
        },
    )

    resp = await client.call(
        system="",
        messages=[_user("compute")],
        tools=[ToolSpec(name="calculator", description="adds", schema={"type": "object"})],
    )

    assert resp.content == "calling tool"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "calculator"
    assert resp.tool_calls[0].arguments == {"a": 1, "b": 2}
    assert resp.stop_reason == "tool_use"


@pytest.mark.asyncio
async def test_call_hoists_empty_system_to_none(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "claude-sonnet-4-7",
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    )

    await client.call(system="", messages=[_user("hi")])

    assert fake_runner.create_calls[0].system is None


@pytest.mark.asyncio
async def test_call_passes_through_tool_specs(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "claude-sonnet-4-7",
            "content": [{"type": "text", "text": ""}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    )
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
    await client.call(
        system="",
        messages=[_user("hi")],
        tools=[ToolSpec(name="t", description="d", schema=schema)],
    )

    tools_arg = fake_runner.create_calls[0].tools
    assert tools_arg is not None
    assert tools_arg[0] == {"name": "t", "description": "d", "input_schema": schema}


@pytest.mark.asyncio
async def test_call_maps_unknown_stop_reason_to_other(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "claude-sonnet-4-7",
            "content": [{"type": "text", "text": "x"}],
            "stop_reason": "weird_new_reason",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    resp = await client.call(system="", messages=[_user("hi")])
    assert resp.stop_reason == "other"


@pytest.mark.asyncio
async def test_call_unknown_model_yields_zero_cost(fake_runner: FakeAnthropicRunner) -> None:
    fake_runner.set_response(
        {
            "model": "private-model",
            "content": [{"type": "text", "text": "x"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        },
    )
    client = AnthropicClient(runner=fake_runner, model_id="private-model")
    resp = await client.call(system="", messages=[_user("hi")])
    assert resp.cost_usd == 0.0


# ----------------------------------------------------------------------
# Tool result + role translation
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_role_messages_encode_as_user_tool_result(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "claude-sonnet-4-7",
            "content": [{"type": "text", "text": ""}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    )
    await client.call(
        system="",
        messages=[Message(role="tool", content="42", tool_call_id="toolu_xyz")],
    )
    sent = fake_runner.create_calls[0].messages[0]
    assert sent["role"] == "user"
    assert sent["content"][0]["type"] == "tool_result"
    assert sent["content"][0]["tool_use_id"] == "toolu_xyz"
    assert sent["content"][0]["content"] == "42"


# ----------------------------------------------------------------------
# call_with_cache
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_with_cache_injects_breakpoint(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "claude-sonnet-4-7",
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 10,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 0,
            },
        },
    )
    resp = await client.call_with_cache(
        system="",
        messages=[_user("turn1"), _user("turn2")],
        cache_breakpoints=[0],
    )
    msgs = fake_runner.create_calls[0].messages
    content0 = msgs[0]["content"]
    assert isinstance(content0, list)
    assert content0[-1]["cache_control"] == {"type": "ephemeral"}
    assert resp.usage.cache_read_tokens == 80


@pytest.mark.asyncio
async def test_call_with_cache_drops_out_of_range_indices(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "claude-sonnet-4-7",
            "content": [{"type": "text", "text": ""}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    )
    await client.call_with_cache(
        system="",
        messages=[_user("only")],
        cache_breakpoints=[0, 99, -1, 0],
    )
    sent = fake_runner.create_calls[0].messages
    assert len(sent) == 1
    assert sent[0]["content"][-1]["cache_control"] == {"type": "ephemeral"}


# ----------------------------------------------------------------------
# call_with_thinking
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_with_thinking_enables_extra_field(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_response(
        {
            "model": "claude-sonnet-4-7",
            "content": [
                {"type": "thinking", "thinking": "let me reason..."},
                {"type": "text", "text": "answer"},
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 20},
        },
    )
    resp = await client.call_with_thinking(
        system="",
        messages=[_user("hard")],
        thinking_budget_tokens=2048,
    )
    extra = fake_runner.create_calls[0].extra
    assert extra["thinking"] == {"type": "enabled", "budget_tokens": 2048}
    assert resp.content == "answer"


@pytest.mark.asyncio
async def test_call_with_thinking_rejects_zero_budget(client: AnthropicClient) -> None:
    with pytest.raises(ValueError, match="thinking_budget_tokens"):
        await client.call_with_thinking(
            system="",
            messages=[_user("hi")],
            thinking_budget_tokens=0,
        )


# ----------------------------------------------------------------------
# stream
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_emits_text_and_terminal_stop_chunk(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_stream_events(
        [
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}},
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "hel"},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "lo"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"input_tokens": 5, "output_tokens": 2},
            },
        ],
    )

    chunks = [chunk async for chunk in client.stream(system="", messages=[_user("hi")])]

    text_chunks = [c for c in chunks if c.kind == "text"]
    assert "".join(c.delta for c in text_chunks) == "hello"
    stop = chunks[-1]
    assert stop.kind == "stop"
    assert stop.stop_reason == "end_turn"
    assert stop.usage is not None
    assert stop.usage.input_tokens == 5
    assert stop.usage.output_tokens == 2


@pytest.mark.asyncio
async def test_stream_buffers_tool_use_input_json(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_stream_events(
        [
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "tool_use", "id": "tu_1", "name": "calc"},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": '{"a":'},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": " 1}"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use"},
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        ],
    )

    chunks = [chunk async for chunk in client.stream(system="", messages=[_user("hi")])]

    tool_chunks = [c for c in chunks if c.kind == "tool_call"]
    assert len(tool_chunks) == 1
    assert tool_chunks[0].tool_call is not None
    assert tool_chunks[0].tool_call.name == "calc"
    assert tool_chunks[0].tool_call.arguments == {"a": 1}


@pytest.mark.asyncio
async def test_stream_thinking_delta_emits_thinking_chunk(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_stream_events(
        [
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": "ponder..."},
            },
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        ],
    )
    chunks = [chunk async for chunk in client.stream(system="", messages=[_user("hi")])]
    thinking = [c for c in chunks if c.kind == "thinking"]
    assert len(thinking) == 1
    assert thinking[0].delta == "ponder..."


@pytest.mark.asyncio
async def test_stream_tool_use_with_malformed_json_yields_empty_args(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    fake_runner.set_stream_events(
        [
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "tool_use", "id": "tu_1", "name": "calc"},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": "{not json"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use"},
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        ],
    )
    chunks = [chunk async for chunk in client.stream(system="", messages=[_user("hi")])]
    tool_chunks = [c for c in chunks if c.kind == "tool_call"]
    assert len(tool_chunks) == 1
    assert tool_chunks[0].tool_call is not None
    assert tool_chunks[0].tool_call.arguments == {}


# ----------------------------------------------------------------------
# Pricing
# ----------------------------------------------------------------------


def test_pricing_strips_dated_suffix() -> None:
    base = compute_cost_usd("claude-sonnet-4-7", input_tokens=1_000_000, output_tokens=0)
    dated = compute_cost_usd("claude-sonnet-4-7-20260301", input_tokens=1_000_000, output_tokens=0)
    assert base == dated
    assert base > 0.0


def test_pricing_unknown_model_returns_zero() -> None:
    assert compute_cost_usd("private-llm", input_tokens=10_000, output_tokens=10_000) == 0.0


# ----------------------------------------------------------------------
# close
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_propagates_to_runner(
    client: AnthropicClient,
    fake_runner: FakeAnthropicRunner,
) -> None:
    assert not fake_runner.closed
    await client.close()
    assert fake_runner.closed


# ----------------------------------------------------------------------
# Default-raise behaviour for capabilities we DON'T declare.
# ----------------------------------------------------------------------


def test_supports_returns_false_for_undeclared_capability(client: AnthropicClient) -> None:
    assert not client.supports("parallel_tools")


@pytest.mark.asyncio
async def test_inherited_default_raise_on_undeclared_capability() -> None:
    from agentforge_core.contracts.llm import LLMClient as _Base  # noqa: PLC0415

    class _NoCaps(_Base):  # type: ignore[misc]
        async def call(  # type: ignore[override]
            self,
            system: str,
            messages: list[object],
            tools: object = None,
        ) -> object:
            return None

        async def close(self) -> None:
            return None

    no = _NoCaps()
    with pytest.raises(CapabilityNotSupported):
        await no.call_with_cache(system="", messages=[], cache_breakpoints=[])
