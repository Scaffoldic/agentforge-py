"""Unit tests for `BedrockClient.call_with_cache` and `call_with_thinking`.

These exercise the chunk-3 capability extensions: prompt caching via
Bedrock cachePoint blocks and Anthropic extended thinking via
additionalModelRequestFields.thinking. The driver shares its retry,
error-mapping, and response-normalisation paths with `call()`, so we
focus on what's specific: request shape, response handling, and
input validation.
"""

from __future__ import annotations

import pytest
from agentforge_bedrock.client import BedrockClient
from agentforge_core.values.messages import Message

from tests.conftest import _FakeBedrockClient, _FakeSession, converse_response

_HAIKU = "anthropic.claude-3-haiku-20240307-v1:0"


def _client(session: _FakeSession) -> BedrockClient:
    return BedrockClient(model_id=_HAIKU, session=session)


# ---- call_with_cache: cache point injection ----


@pytest.mark.asyncio
async def test_cache_point_injected_after_indexed_message(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response())
    client = _client(fake_session)
    await client.call_with_cache(
        "sys",
        [
            Message(role="user", content="long context A"),
            Message(role="assistant", content="ack"),
            Message(role="user", content="question"),
        ],
        cache_breakpoints=[1],  # cache the conversation prefix through the assistant turn
    )
    sent = fake_bedrock.calls[0]
    # Message 0 (user) — no cache point
    assert sent["messages"][0]["content"] == [{"text": "long context A"}]
    # Message 1 (assistant) — cache point appended after the text
    assert sent["messages"][1]["content"] == [
        {"text": "ack"},
        {"cachePoint": {"type": "default"}},
    ]
    # Message 2 — no cache point
    assert sent["messages"][2]["content"] == [{"text": "question"}]


@pytest.mark.asyncio
async def test_cache_point_with_multiple_breakpoints(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response())
    client = _client(fake_session)
    await client.call_with_cache(
        "sys",
        [Message(role="user", content=f"msg {i}") for i in range(4)],
        cache_breakpoints=[0, 2],
    )
    contents = [m["content"] for m in fake_bedrock.calls[0]["messages"]]
    assert {"cachePoint": {"type": "default"}} in contents[0]
    assert {"cachePoint": {"type": "default"}} not in contents[1]
    assert {"cachePoint": {"type": "default"}} in contents[2]
    assert {"cachePoint": {"type": "default"}} not in contents[3]


@pytest.mark.asyncio
async def test_cache_point_out_of_range_indices_silently_dropped(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """Negative or too-large indices are dropped rather than raising
    so callers that compute breakpoints from token counts don't crash
    on edge cases."""
    fake_bedrock.responses.append(converse_response())
    client = _client(fake_session)
    await client.call_with_cache(
        "sys",
        [Message(role="user", content="only message")],
        cache_breakpoints=[-1, 5, 0],
    )
    sent = fake_bedrock.calls[0]
    # Only index 0 was valid
    assert sent["messages"][0]["content"] == [
        {"text": "only message"},
        {"cachePoint": {"type": "default"}},
    ]


@pytest.mark.asyncio
async def test_cache_point_duplicate_breakpoints_only_inserted_once(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response())
    client = _client(fake_session)
    await client.call_with_cache(
        "sys",
        [Message(role="user", content="ctx")],
        cache_breakpoints=[0, 0, 0],
    )
    content = fake_bedrock.calls[0]["messages"][0]["content"]
    cache_blocks = [b for b in content if "cachePoint" in b]
    assert len(cache_blocks) == 1


@pytest.mark.asyncio
async def test_cache_point_empty_breakpoints_means_no_caching(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """Empty breakpoints is a valid request — equivalent to plain call.
    Useful when caller computes breakpoints dynamically and the result
    happens to be empty."""
    fake_bedrock.responses.append(converse_response())
    client = _client(fake_session)
    await client.call_with_cache("sys", [Message(role="user", content="hi")], cache_breakpoints=[])
    content = fake_bedrock.calls[0]["messages"][0]["content"]
    assert content == [{"text": "hi"}]


@pytest.mark.asyncio
async def test_cache_response_surfaces_cache_token_metrics(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """Bedrock's CacheReadInputTokens / CacheWriteInputTokens come back
    in the response usage; the driver propagates them onto TokenUsage."""
    response = converse_response(text="cached answer")
    response["usage"]["cacheReadInputTokens"] = 800
    response["usage"]["cacheWriteInputTokens"] = 200
    fake_bedrock.responses.append(response)

    client = _client(fake_session)
    resp = await client.call_with_cache(
        "sys", [Message(role="user", content="hi")], cache_breakpoints=[0]
    )
    assert resp.usage.cache_read_tokens == 800
    assert resp.usage.cache_write_tokens == 200


# ---- call_with_thinking: additionalModelRequestFields shape ----


@pytest.mark.asyncio
async def test_thinking_sets_additional_model_request_fields(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response(text="answer"))
    client = _client(fake_session)
    await client.call_with_thinking(
        "sys",
        [Message(role="user", content="solve this")],
        thinking_budget_tokens=1024,
    )
    sent = fake_bedrock.calls[0]
    assert sent["additionalModelRequestFields"] == {
        "thinking": {"type": "enabled", "budget_tokens": 1024},
    }


@pytest.mark.asyncio
async def test_thinking_response_drops_reasoning_content_blocks(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """Bedrock returns reasoningContent alongside text; only the text
    surfaces in LLMResponse.content (the public answer)."""
    fake_bedrock.responses.append(
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "reasoningContent": {
                                "reasoningText": {
                                    "text": "Let me think step by step...",
                                    "signature": "abc123",
                                }
                            }
                        },
                        {"text": "The answer is 42."},
                    ],
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 50, "totalTokens": 60},
        }
    )
    client = _client(fake_session)
    resp = await client.call_with_thinking(
        "sys",
        [Message(role="user", content="what is the answer")],
        thinking_budget_tokens=500,
    )
    assert resp.content == "The answer is 42."
    # No reasoning text leaked into the public answer.
    assert "step by step" not in resp.content


@pytest.mark.asyncio
async def test_thinking_rejects_zero_or_negative_budget(
    fake_session: _FakeSession,
) -> None:
    client = _client(fake_session)
    with pytest.raises(ValueError, match="thinking_budget_tokens"):
        await client.call_with_thinking(
            "sys", [Message(role="user", content="hi")], thinking_budget_tokens=0
        )
    with pytest.raises(ValueError, match="thinking_budget_tokens"):
        await client.call_with_thinking(
            "sys", [Message(role="user", content="hi")], thinking_budget_tokens=-1
        )


@pytest.mark.asyncio
async def test_thinking_preserves_normal_response_path(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """The response goes through the same retry + normalise path as
    `call()` — cost/usage/stop-reason are normalised the same way."""
    fake_bedrock.responses.append(converse_response(text="ok", input_tokens=10, output_tokens=20))
    client = _client(fake_session)
    resp = await client.call_with_thinking(
        "sys", [Message(role="user", content="hi")], thinking_budget_tokens=200
    )
    assert resp.content == "ok"
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 20
    assert resp.cost_usd > 0


# ---- Composition: cache + thinking are independent (caller picks one per call) ----


@pytest.mark.asyncio
async def test_call_does_not_emit_cache_or_thinking_fields(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """Plain call() must not include cachePoint blocks or
    additionalModelRequestFields.thinking — those only appear when
    the caller invokes the dedicated capability methods."""
    fake_bedrock.responses.append(converse_response())
    client = _client(fake_session)
    await client.call("sys", [Message(role="user", content="hi")])
    sent = fake_bedrock.calls[0]
    assert "additionalModelRequestFields" not in sent
    assert all(not any("cachePoint" in b for b in m.get("content", [])) for m in sent["messages"])


# ---- Cache + tools: cache point doesn't displace tool blocks ----


@pytest.mark.asyncio
async def test_cache_point_appended_after_existing_tool_result_blocks(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """A tool-result message has a content list with a toolResult block;
    the cache point appends after it."""
    fake_bedrock.responses.append(converse_response())
    client = _client(fake_session)
    await client.call_with_cache(
        "sys",
        [
            Message(role="user", content="ask"),
            Message(role="tool", tool_call_id="tu_1", content="result"),
        ],
        cache_breakpoints=[1],
    )
    content = fake_bedrock.calls[0]["messages"][1]["content"]
    # Should be [toolResult, cachePoint] in that order.
    assert "toolResult" in content[0]
    assert content[-1] == {"cachePoint": {"type": "default"}}
