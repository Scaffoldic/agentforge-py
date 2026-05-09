"""Unit tests for `BedrockClient.stream()` over Bedrock ConverseStream.

The driver normalises Bedrock's event sequence into our
`StreamChunk` vocabulary (text / thinking / tool_call / stop). Tests
script event sequences against a fake bedrock-runtime client and
assert the emitted chunks.
"""

from __future__ import annotations

import pytest
from agentforge_bedrock import accumulate_stream
from agentforge_bedrock.client import BedrockClient
from agentforge_core.production.exceptions import (
    ProviderError,
    RateLimitError,
)
from agentforge_core.values.messages import Message, StreamChunk
from botocore.exceptions import ClientError

from tests.conftest import _FakeBedrockClient, _FakeSession

_HAIKU = "anthropic.claude-3-haiku-20240307-v1:0"


def _client(session: _FakeSession) -> BedrockClient:
    return BedrockClient(model_id=_HAIKU, session=session)


# ---- Text streaming ----


@pytest.mark.asyncio
async def test_stream_yields_text_then_terminal_stop_chunk(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.stream_responses.append(
        [
            {"messageStart": {"role": "assistant"}},
            {"contentBlockDelta": {"delta": {"text": "hello"}, "contentBlockIndex": 0}},
            {"contentBlockDelta": {"delta": {"text": " "}, "contentBlockIndex": 0}},
            {"contentBlockDelta": {"delta": {"text": "world"}, "contentBlockIndex": 0}},
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "end_turn"}},
            {
                "metadata": {
                    "usage": {"inputTokens": 5, "outputTokens": 3, "totalTokens": 8},
                    "metrics": {"latencyMs": 100},
                }
            },
        ]
    )
    client = _client(fake_session)
    chunks: list[StreamChunk] = [
        c async for c in client.stream("sys", [Message(role="user", content="hi")])
    ]
    text_chunks = [c for c in chunks if c.kind == "text"]
    assert "".join(c.delta for c in text_chunks) == "hello world"
    # Exactly one terminal stop chunk.
    stop = chunks[-1]
    assert stop.kind == "stop"
    assert stop.stop_reason == "end_turn"
    assert stop.usage is not None
    assert stop.usage.input_tokens == 5
    assert stop.usage.output_tokens == 3
    assert stop.cost_usd > 0  # haiku is in the price table


# ---- Thinking deltas ----


@pytest.mark.asyncio
async def test_stream_emits_thinking_chunks_for_reasoning_content(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.stream_responses.append(
        [
            {"messageStart": {"role": "assistant"}},
            {
                "contentBlockDelta": {
                    "delta": {"reasoningContent": {"text": "Step 1: ..."}},
                    "contentBlockIndex": 0,
                }
            },
            {
                "contentBlockDelta": {
                    "delta": {"reasoningContent": {"text": "Step 2: ..."}},
                    "contentBlockIndex": 0,
                }
            },
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"contentBlockDelta": {"delta": {"text": "answer"}, "contentBlockIndex": 1}},
            {"contentBlockStop": {"contentBlockIndex": 1}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1}}},
        ]
    )
    client = _client(fake_session)
    chunks: list[StreamChunk] = [
        c async for c in client.stream("sys", [Message(role="user", content="hi")])
    ]
    thinking = [c for c in chunks if c.kind == "thinking"]
    text = [c for c in chunks if c.kind == "text"]
    assert [c.delta for c in thinking] == ["Step 1: ...", "Step 2: ..."]
    assert [c.delta for c in text] == ["answer"]


@pytest.mark.asyncio
async def test_stream_skips_reasoning_signature_only_deltas(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """`reasoningContent` deltas with only a `signature` (no text) are
    bookkeeping; we don't emit empty thinking chunks for them."""
    fake_bedrock.stream_responses.append(
        [
            {
                "contentBlockDelta": {
                    "delta": {"reasoningContent": {"signature": "abc"}},
                    "contentBlockIndex": 0,
                }
            },
            {"contentBlockDelta": {"delta": {"text": "hi"}, "contentBlockIndex": 1}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1}}},
        ]
    )
    client = _client(fake_session)
    chunks: list[StreamChunk] = [
        c async for c in client.stream("sys", [Message(role="user", content="hi")])
    ]
    thinking = [c for c in chunks if c.kind == "thinking"]
    assert thinking == []


# ---- Tool-use streaming ----


@pytest.mark.asyncio
async def test_stream_accumulates_tool_use_input_across_deltas(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.stream_responses.append(
        [
            {
                "contentBlockStart": {
                    "start": {"toolUse": {"toolUseId": "tu_1", "name": "search"}},
                    "contentBlockIndex": 0,
                }
            },
            {
                "contentBlockDelta": {
                    "delta": {"toolUse": {"input": '{"query":'}},
                    "contentBlockIndex": 0,
                }
            },
            {
                "contentBlockDelta": {
                    "delta": {"toolUse": {"input": ' "agentforge"}'}},
                    "contentBlockIndex": 0,
                }
            },
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "tool_use"}},
            {"metadata": {"usage": {"inputTokens": 4, "outputTokens": 4}}},
        ]
    )
    client = _client(fake_session)
    chunks: list[StreamChunk] = [
        c async for c in client.stream("sys", [Message(role="user", content="search")])
    ]
    tool_calls = [c for c in chunks if c.kind == "tool_call"]
    assert len(tool_calls) == 1
    tc = tool_calls[0].tool_call
    assert tc is not None
    assert tc.id == "tu_1"
    assert tc.name == "search"
    assert tc.arguments == {"query": "agentforge"}
    # The terminal stop reflects tool_use.
    stop = chunks[-1]
    assert stop.stop_reason == "tool_use"


@pytest.mark.asyncio
async def test_stream_invalid_tool_use_json_yields_empty_arguments(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """Truncated/invalid tool-use input JSON falls back to empty
    arguments rather than crashing the stream consumer."""
    fake_bedrock.stream_responses.append(
        [
            {
                "contentBlockStart": {
                    "start": {"toolUse": {"toolUseId": "tu_1", "name": "search"}},
                    "contentBlockIndex": 0,
                }
            },
            {
                "contentBlockDelta": {
                    "delta": {"toolUse": {"input": '{"query": "ai'}},
                    "contentBlockIndex": 0,
                }
            },
            # No closing brace — truncated JSON.
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "max_tokens"}},
            {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1}}},
        ]
    )
    client = _client(fake_session)
    chunks: list[StreamChunk] = [
        c async for c in client.stream("sys", [Message(role="user", content="x")])
    ]
    tool_calls = [c for c in chunks if c.kind == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_call is not None
    assert tool_calls[0].tool_call.arguments == {}


# ---- Error mapping on stream open ----


def _client_error(code: str, message: str = "boom", status: int = 400) -> ClientError:
    return ClientError(
        error_response={
            "Error": {"Code": code, "Message": message},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        operation_name="ConverseStream",
    )


@pytest.mark.asyncio
async def test_stream_open_error_maps_through_provider_error(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.stream_responses.append(_client_error("ThrottlingException"))
    client = _client(fake_session)
    with pytest.raises(RateLimitError):
        async for _ in client.stream("sys", [Message(role="user", content="x")]):
            pass


@pytest.mark.asyncio
async def test_stream_unknown_error_maps_to_provider_error(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.stream_responses.append(_client_error("MysteryException"))
    client = _client(fake_session)
    with pytest.raises(ProviderError):
        async for _ in client.stream("sys", [Message(role="user", content="x")]):
            pass


# ---- Empty / minimal streams ----


@pytest.mark.asyncio
async def test_stream_with_only_metadata_emits_zero_text_then_stop(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """A stream that produces only a stop reason and metadata (no
    content) still yields exactly one terminal stop chunk."""
    fake_bedrock.stream_responses.append(
        [
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 2, "outputTokens": 0}}},
        ]
    )
    client = _client(fake_session)
    chunks: list[StreamChunk] = [
        c async for c in client.stream("sys", [Message(role="user", content="x")])
    ]
    assert len(chunks) == 1
    assert chunks[0].kind == "stop"


@pytest.mark.asyncio
async def test_stream_request_shape_matches_call_shape(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """The same request builder is used for converse_stream as for
    converse, so the request shapes match (modelId, messages, etc.)."""
    fake_bedrock.stream_responses.append(
        [
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1}}},
        ]
    )
    client = _client(fake_session)
    async for _ in client.stream("you are helpful", [Message(role="user", content="hi")]):
        pass
    sent = fake_bedrock.stream_calls[0]
    assert sent["modelId"] == _HAIKU
    assert sent["system"] == [{"text": "you are helpful"}]
    assert sent["messages"] == [{"role": "user", "content": [{"text": "hi"}]}]


# ---- accumulate_stream helper ----


@pytest.mark.asyncio
async def test_accumulate_stream_collapses_chunks_into_llm_response(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.stream_responses.append(
        [
            {"contentBlockDelta": {"delta": {"text": "hello "}, "contentBlockIndex": 0}},
            {"contentBlockDelta": {"delta": {"text": "world"}, "contentBlockIndex": 0}},
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 5, "outputTokens": 5}}},
        ]
    )
    client = _client(fake_session)
    resp = await accumulate_stream(client.stream("sys", [Message(role="user", content="hi")]))
    assert resp.content == "hello world"
    assert resp.stop_reason == "end_turn"
    assert resp.usage.input_tokens == 5
    assert resp.cost_usd > 0


@pytest.mark.asyncio
async def test_accumulate_stream_drops_thinking_from_content(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """Thinking chunks are visible to streaming consumers but excluded
    from the public `content` of the accumulated response."""
    fake_bedrock.stream_responses.append(
        [
            {
                "contentBlockDelta": {
                    "delta": {"reasoningContent": {"text": "internal thought"}},
                    "contentBlockIndex": 0,
                }
            },
            {"contentBlockDelta": {"delta": {"text": "final answer"}, "contentBlockIndex": 1}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 5}}},
        ]
    )
    client = _client(fake_session)
    resp = await accumulate_stream(client.stream("sys", [Message(role="user", content="hi")]))
    assert resp.content == "final answer"
    assert "internal thought" not in resp.content


@pytest.mark.asyncio
async def test_accumulate_stream_carries_tool_calls(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.stream_responses.append(
        [
            {
                "contentBlockStart": {
                    "start": {"toolUse": {"toolUseId": "tu_1", "name": "search"}},
                    "contentBlockIndex": 0,
                }
            },
            {
                "contentBlockDelta": {
                    "delta": {"toolUse": {"input": '{"q": "x"}'}},
                    "contentBlockIndex": 0,
                }
            },
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "tool_use"}},
            {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1}}},
        ]
    )
    client = _client(fake_session)
    resp = await accumulate_stream(client.stream("sys", [Message(role="user", content="x")]))
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "search"
    assert resp.tool_calls[0].arguments == {"q": "x"}
    assert resp.stop_reason == "tool_use"
