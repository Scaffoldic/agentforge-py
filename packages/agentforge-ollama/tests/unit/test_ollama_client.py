"""Unit tests for `OllamaClient`."""

from __future__ import annotations

import pytest
from agentforge_core.values.messages import Message, ToolSpec
from agentforge_ollama import OllamaClient
from agentforge_ollama._inmem_runner import FakeOllamaRunner


def _user(text: str) -> Message:
    return Message(role="user", content=text)


def test_constructor_rejects_empty_model(fake_runner: FakeOllamaRunner) -> None:
    with pytest.raises(ValueError, match="model_id"):
        OllamaClient(runner=fake_runner, model_id="")


def test_constructor_rejects_zero_timeout(fake_runner: FakeOllamaRunner) -> None:
    with pytest.raises(ValueError, match="timeout"):
        OllamaClient(runner=fake_runner, model_id="x", timeout_seconds=0)


def test_capabilities_includes_tools_when_supported(fake_runner: FakeOllamaRunner) -> None:
    c = OllamaClient(runner=fake_runner, model_id="llama3.2:3b")
    assert c.capabilities() == {"tools", "streaming"}


def test_capabilities_drops_tools_when_disabled(fake_runner: FakeOllamaRunner) -> None:
    c = OllamaClient(runner=fake_runner, model_id="llama3.2:3b", supports_tools=False)
    assert c.capabilities() == {"streaming"}


@pytest.mark.asyncio
async def test_call_normalises_text_response(
    client: OllamaClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    fake_runner.set_chat_response(
        {
            "model": "llama3.2:3b",
            "message": {"role": "assistant", "content": "hello"},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 5,
        },
    )
    resp = await client.call(system="be brief", messages=[_user("hi")])
    assert resp.content == "hello"
    assert resp.stop_reason == "end_turn"
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 5
    assert resp.cost_usd == 0.0
    assert resp.provider == "ollama"


@pytest.mark.asyncio
async def test_call_normalises_tool_calls(
    client: OllamaClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    fake_runner.set_chat_response(
        {
            "model": "llama3.2:3b",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "calc", "arguments": {"a": 2}}},
                ],
            },
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 1,
            "eval_count": 1,
        },
    )
    resp = await client.call(
        system="",
        messages=[_user("compute")],
        tools=[ToolSpec(name="calc", description="adds", schema={"type": "object"})],
    )
    assert resp.tool_calls[0].name == "calc"
    assert resp.tool_calls[0].arguments == {"a": 2}
    # done_reason=stop + tool_calls present → tool_use stop reason.
    assert resp.stop_reason == "tool_use"


@pytest.mark.asyncio
async def test_call_omits_tools_when_unsupported(fake_runner: FakeOllamaRunner) -> None:
    fake_runner.set_chat_response(
        {
            "model": "x",
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "done_reason": "stop",
        },
    )
    c = OllamaClient(runner=fake_runner, model_id="x", supports_tools=False)
    await c.call(
        system="",
        messages=[_user("hi")],
        tools=[ToolSpec(name="t", description="d", schema={"type": "object"})],
    )
    assert fake_runner.chat_calls[0].tools is None


@pytest.mark.asyncio
async def test_call_hoists_system_when_present(
    client: OllamaClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    fake_runner.set_chat_response(
        {
            "model": "x",
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "done_reason": "stop",
        },
    )
    await client.call(system="ROLE", messages=[_user("hi")])
    msgs = fake_runner.chat_calls[0].messages
    assert msgs[0] == {"role": "system", "content": "ROLE"}


@pytest.mark.asyncio
async def test_call_done_reason_length_maps_to_max_tokens(
    client: OllamaClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    fake_runner.set_chat_response(
        {
            "model": "x",
            "message": {"role": "assistant", "content": "..."},
            "done": True,
            "done_reason": "length",
        },
    )
    resp = await client.call(system="", messages=[_user("hi")])
    assert resp.stop_reason == "max_tokens"


@pytest.mark.asyncio
async def test_call_unknown_done_reason_maps_to_other(
    client: OllamaClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    fake_runner.set_chat_response(
        {
            "model": "x",
            "message": {"role": "assistant", "content": "x"},
            "done": True,
            "done_reason": "exotic",
        },
    )
    resp = await client.call(system="", messages=[_user("hi")])
    assert resp.stop_reason == "other"


@pytest.mark.asyncio
async def test_stream_emits_text_and_terminal_stop(
    client: OllamaClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    fake_runner.set_stream_events(
        [
            {"message": {"content": "hel"}, "done": False},
            {"message": {"content": "lo"}, "done": False},
            {
                "message": {"content": ""},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 4,
                "eval_count": 2,
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
    assert stop.usage.input_tokens == 4


@pytest.mark.asyncio
async def test_stream_emits_tool_call_chunks(
    client: OllamaClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    fake_runner.set_stream_events(
        [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "calc", "arguments": {"a": 1}}},
                    ],
                },
                "done": False,
            },
            {
                "message": {"content": ""},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
            },
        ],
    )
    chunks = [c async for c in client.stream(system="", messages=[_user("hi")])]
    tool_chunks = [c for c in chunks if c.kind == "tool_call"]
    assert len(tool_chunks) == 1
    assert tool_chunks[0].tool_call is not None
    assert tool_chunks[0].tool_call.name == "calc"


@pytest.mark.asyncio
async def test_close_propagates(
    client: OllamaClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    await client.close()
    assert fake_runner.closed
