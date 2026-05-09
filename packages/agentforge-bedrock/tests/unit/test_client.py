"""Unit tests for `BedrockClient.call()` end-to-end against a fake boto3."""

from __future__ import annotations

from typing import Any

import pytest
from agentforge_bedrock import _retry as retry_mod
from agentforge_bedrock.client import BedrockClient
from agentforge_core.production.exceptions import (
    AuthenticationError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    ServiceError,
)
from agentforge_core.resolver import Resolver
from agentforge_core.values.messages import Message, ToolSpec
from botocore.exceptions import ClientError

from tests.conftest import _FakeBedrockClient, _FakeSession, converse_response


async def _no_sleep(_seconds: float) -> None:
    return None


# ---- Constructor validation ----


def test_constructor_rejects_empty_model_id() -> None:
    with pytest.raises(ValueError, match="model_id"):
        BedrockClient(model_id="")


def test_constructor_rejects_negative_max_retries() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", max_retries=-1)


def test_constructor_rejects_zero_timeout() -> None:
    with pytest.raises(ValueError, match="timeout"):
        BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", timeout_seconds=0)


def test_default_region_falls_back_to_us_east_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_REGION", raising=False)
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0")
    assert client._region == "us-east-1"


def test_region_uses_aws_region_env_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0")
    assert client._region == "us-west-2"


def test_explicit_region_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", region="eu-west-1")
    assert client._region == "eu-west-1"


# ---- Provider registration ----


def test_registered_under_providers_bedrock() -> None:
    cls = Resolver.global_().resolve("providers", "bedrock")
    assert cls is BedrockClient


# ---- Capabilities ----


def test_declares_tools_json_mode_caching_thinking() -> None:
    """tools+json_mode shipped in chunk 2; caching+thinking in chunk 3.
    streaming lights up in chunk 4."""
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0")
    assert client.supports("tools")
    assert client.supports("json_mode")
    assert client.supports("caching")
    assert client.supports("thinking")
    assert not client.supports("streaming")


# ---- call() happy path ----


@pytest.mark.asyncio
async def test_call_returns_normalised_response(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(
        converse_response(text="hello world", input_tokens=20, output_tokens=8)
    )
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    resp = await client.call("you are helpful", [Message(role="user", content="hi")])

    assert resp.content == "hello world"
    assert resp.stop_reason == "end_turn"
    assert resp.usage.input_tokens == 20
    assert resp.usage.output_tokens == 8
    assert resp.model == "anthropic.claude-3-haiku-20240307-v1:0"
    assert resp.provider == "bedrock"
    # cost_usd > 0 because Haiku is in the price table
    assert resp.cost_usd > 0


@pytest.mark.asyncio
async def test_call_strips_inference_prefix_for_pricing(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """Cross-region IDs (us./global./...) bill at the base model rate."""
    fake_bedrock.responses.append(converse_response(input_tokens=10, output_tokens=10))
    client = BedrockClient(
        model_id="us.anthropic.claude-3-haiku-20240307-v1:0", session=fake_session
    )
    resp = await client.call("sys", [Message(role="user", content="hi")])
    assert resp.cost_usd > 0
    # The model id is preserved on the response (not the stripped form).
    assert resp.model == "us.anthropic.claude-3-haiku-20240307-v1:0"


@pytest.mark.asyncio
async def test_call_emits_tool_calls_from_tool_use_blocks(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(
        converse_response(
            text="thinking...",
            stop_reason="tool_use",
            tool_use={
                "toolUseId": "tu_1",
                "name": "search",
                "input": {"query": "agentforge"},
            },
        )
    )
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    resp = await client.call("sys", [Message(role="user", content="search")])
    assert resp.stop_reason == "tool_use"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "search"
    assert resp.tool_calls[0].arguments == {"query": "agentforge"}


# ---- Request shape ----


@pytest.mark.asyncio
async def test_call_translates_system_prompt_to_bedrock_system_field(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response())
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    await client.call("you are helpful", [Message(role="user", content="hi")])

    sent = fake_bedrock.calls[0]
    assert sent["system"] == [{"text": "you are helpful"}]
    assert sent["modelId"] == "anthropic.claude-3-haiku-20240307-v1:0"
    assert sent["messages"] == [{"role": "user", "content": [{"text": "hi"}]}]


@pytest.mark.asyncio
async def test_call_omits_system_field_when_empty(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response())
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    await client.call("", [Message(role="user", content="hi")])
    assert "system" not in fake_bedrock.calls[0]


@pytest.mark.asyncio
async def test_call_translates_tool_messages_to_tool_results(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response())
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    await client.call(
        "sys",
        [
            Message(role="user", content="what time"),
            Message(role="tool", tool_call_id="tu_1", content='{"now": "noon"}'),
        ],
    )
    sent_messages = fake_bedrock.calls[0]["messages"]
    # Tool result is encoded as a user message with toolResult content.
    assert sent_messages[1]["role"] == "user"
    assert sent_messages[1]["content"][0]["toolResult"]["toolUseId"] == "tu_1"


@pytest.mark.asyncio
async def test_call_translates_tools_to_toolconfig(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response())
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    spec = ToolSpec(
        name="search",
        description="search the web",
        schema={"type": "object", "properties": {"q": {"type": "string"}}},
    )
    await client.call("sys", [Message(role="user", content="hi")], tools=[spec])

    sent = fake_bedrock.calls[0]
    assert "toolConfig" in sent
    tools_sent = sent["toolConfig"]["tools"]
    assert tools_sent[0]["toolSpec"]["name"] == "search"
    assert tools_sent[0]["toolSpec"]["inputSchema"]["json"]["type"] == "object"


# ---- Error mapping ----


def _client_error(code: str, message: str = "boom", status: int = 400) -> ClientError:
    return ClientError(
        error_response={
            "Error": {"Code": code, "Message": message},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        operation_name="Converse",
    )


@pytest.mark.asyncio
async def test_throttling_error_maps_to_rate_limit_error(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    # 4 throttles in a row exhausts the retry budget (max_retries=3).
    fake_bedrock.responses.extend([_client_error("ThrottlingException", "rate limited")] * 4)
    client = BedrockClient(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        session=fake_session,
        max_retries=3,
    )
    with pytest.raises(RateLimitError, match="throttled"):
        await client.call("sys", [Message(role="user", content="hi")])


@pytest.mark.asyncio
async def test_throttling_then_success_succeeds_via_retry(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One transient throttle followed by success returns the success."""
    monkeypatch.setattr(retry_mod.asyncio, "sleep", _no_sleep)

    fake_bedrock.responses.extend(
        [
            _client_error("ThrottlingException"),
            converse_response(text="recovered"),
        ]
    )
    client = BedrockClient(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        session=fake_session,
        max_retries=2,
    )
    resp = await client.call("sys", [Message(role="user", content="hi")])
    assert resp.content == "recovered"
    assert len(fake_bedrock.calls) == 2


@pytest.mark.asyncio
async def test_access_denied_maps_to_authentication_error(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(_client_error("AccessDeniedException", status=403))
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    with pytest.raises(AuthenticationError):
        await client.call("sys", [Message(role="user", content="hi")])


@pytest.mark.asyncio
async def test_resource_not_found_maps_to_model_not_found_error(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(_client_error("ResourceNotFoundException", status=404))
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    with pytest.raises(ModelNotFoundError):
        await client.call("sys", [Message(role="user", content="hi")])


@pytest.mark.asyncio
async def test_validation_error_with_model_message_maps_to_model_not_found(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(_client_error("ValidationException", "invalid modelId"))
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    with pytest.raises(ModelNotFoundError):
        await client.call("sys", [Message(role="user", content="hi")])


@pytest.mark.asyncio
async def test_internal_server_error_maps_to_service_error_after_retries(
    fake_bedrock: _FakeBedrockClient,
    fake_session: _FakeSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(retry_mod.asyncio, "sleep", _no_sleep)

    fake_bedrock.responses.extend([_client_error("InternalServerException", status=500)] * 4)
    client = BedrockClient(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        session=fake_session,
        max_retries=3,
    )
    with pytest.raises(ServiceError):
        await client.call("sys", [Message(role="user", content="hi")])


@pytest.mark.asyncio
async def test_unknown_error_code_maps_to_generic_provider_error(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(_client_error("WeirdNewException"))
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    with pytest.raises(ProviderError):
        await client.call("sys", [Message(role="user", content="hi")])


# ---- close() ----


@pytest.mark.asyncio
async def test_close_releases_client(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response())
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    await client.call("sys", [Message(role="user", content="hi")])
    assert client._client is not None
    await client.close()
    assert client._client is None


@pytest.mark.asyncio
async def test_close_is_idempotent_when_never_called(
    fake_session: _FakeSession,
) -> None:
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    await client.close()
    await client.close()


# ---- Stop-reason normalisation ----


@pytest.mark.asyncio
async def test_guardrail_stop_reason_normalises_to_other(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(
        converse_response(text="filtered", stop_reason="guardrail_intervened")
    )
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    resp = await client.call("sys", [Message(role="user", content="hi")])
    assert resp.stop_reason == "other"


# ---- Cache token surfacing ----


@pytest.mark.asyncio
async def test_cache_tokens_propagate_into_token_usage(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    response = converse_response()
    response["usage"]["cacheReadInputTokens"] = 100
    response["usage"]["cacheWriteInputTokens"] = 50
    fake_bedrock.responses.append(response)
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    resp = await client.call("sys", [Message(role="user", content="hi")])
    assert resp.usage.cache_read_tokens == 100
    assert resp.usage.cache_write_tokens == 50


# ---- Unknown model: cost defaults to zero, no crash ----


@pytest.mark.asyncio
async def test_unknown_model_returns_zero_cost(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response(input_tokens=100, output_tokens=50))
    client = BedrockClient(
        model_id="anthropic.totally-not-a-real-model-v999:0", session=fake_session
    )
    resp = await client.call("sys", [Message(role="user", content="hi")])
    assert resp.cost_usd == 0.0


# ---- Smoke: many messages translate cleanly ----


@pytest.mark.asyncio
async def test_multi_turn_conversation_translates_each_role(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.responses.append(converse_response())
    client = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=fake_session)
    await client.call(
        "sys",
        [
            Message(role="user", content="hi"),
            Message(role="assistant", content="hello"),
            Message(role="user", content="bye"),
        ],
    )
    sent_messages: list[dict[str, Any]] = fake_bedrock.calls[0]["messages"]
    assert [m["role"] for m in sent_messages] == ["user", "assistant", "user"]
