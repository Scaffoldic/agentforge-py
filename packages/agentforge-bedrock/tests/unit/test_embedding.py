"""Unit tests for `BedrockEmbeddingClient`."""

from __future__ import annotations

import json as _json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from agentforge_bedrock import _retry as retry_mod
from agentforge_bedrock.embedding import BedrockEmbeddingClient
from agentforge_core.production.exceptions import (
    ModelNotFoundError,
    RateLimitError,
)
from agentforge_core.resolver import Resolver
from agentforge_core.testing import run_embedding_conformance
from botocore.exceptions import ClientError

from tests.conftest import _FakeBedrockClient, _FakeSession


async def _no_sleep(_seconds: float) -> None:
    return None


_TITAN = "amazon.titan-embed-text-v2:0"
_COHERE = "cohere.embed-english-v3"


def _client(session: _FakeSession, model_id: str = _TITAN) -> BedrockEmbeddingClient:
    return BedrockEmbeddingClient(model_id=model_id, session=session)


# ---- Constructor + registration ----


def test_constructor_rejects_empty_model_id() -> None:
    with pytest.raises(ValueError, match="model_id"):
        BedrockEmbeddingClient(model_id="")


def test_constructor_rejects_negative_max_retries() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        BedrockEmbeddingClient(model_id=_TITAN, max_retries=-1)


def test_constructor_rejects_zero_timeout() -> None:
    with pytest.raises(ValueError, match="timeout"):
        BedrockEmbeddingClient(model_id=_TITAN, timeout_seconds=0)


def test_registered_under_embeddings_bedrock() -> None:
    cls = Resolver.global_().resolve("embeddings", "bedrock")
    assert cls is BedrockEmbeddingClient


# ---- dimensions() resolution ----


def test_dimensions_resolved_from_price_table_for_titan_v2() -> None:
    client = BedrockEmbeddingClient(model_id="amazon.titan-embed-text-v2:0")
    assert client.dimensions() == 1024


def test_dimensions_resolved_from_price_table_for_titan_v1() -> None:
    client = BedrockEmbeddingClient(model_id="amazon.titan-embed-text-v1")
    assert client.dimensions() == 1536


def test_dimensions_resolved_from_price_table_for_cohere() -> None:
    client = BedrockEmbeddingClient(model_id="cohere.embed-english-v3")
    assert client.dimensions() == 1024


def test_dimensions_falls_back_to_default_for_unknown_model() -> None:
    """Unknown models fall back to the conservative default (1024)
    rather than raising at construction — callers can still embed,
    cost just shows zero."""
    client = BedrockEmbeddingClient(model_id="amazon.titan-embed-future-v999:0")
    assert client.dimensions() == 1024


# ---- Titan: one-text-per-call loop ----


@pytest.mark.asyncio
async def test_embed_titan_loops_per_text(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.invoke_responses.extend(
        [
            {"embedding": [0.1] * 1024, "inputTextTokenCount": 5},
            {"embedding": [0.2] * 1024, "inputTextTokenCount": 7},
        ]
    )
    client = _client(fake_session, _TITAN)
    resp = await client.embed(["hello", "world"])

    # Two InvokeModel calls — one per text
    assert len(fake_bedrock.invoke_calls) == 2
    # Each call payload is a JSON `inputText` request

    first = _json.loads(fake_bedrock.invoke_calls[0]["body"])
    second = _json.loads(fake_bedrock.invoke_calls[1]["body"])
    assert first == {"inputText": "hello"}
    assert second == {"inputText": "world"}

    # Vectors come back in input order
    assert len(resp.vectors) == 2
    assert resp.vectors[0][0] == pytest.approx(0.1)
    assert resp.vectors[1][0] == pytest.approx(0.2)
    # Token usage sums across the loop
    assert resp.usage.input_tokens == 12
    assert resp.usage.output_tokens == 0
    # Cost > 0 since titan v2 is in the price table
    assert resp.cost_usd > 0


# ---- Cohere: native batch ----


@pytest.mark.asyncio
async def test_embed_cohere_uses_native_batch(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.invoke_responses.append(
        {
            "embeddings": [[0.5] * 1024, [0.6] * 1024],
            "id": "abc",
            "response_type": "embeddings_floats",
            "texts": ["hello", "world"],
        }
    )
    client = _client(fake_session, _COHERE)
    resp = await client.embed(["hello", "world"])

    # ONE InvokeModel call — native batch
    assert len(fake_bedrock.invoke_calls) == 1

    body = _json.loads(fake_bedrock.invoke_calls[0]["body"])
    assert body["texts"] == ["hello", "world"]
    assert body["input_type"] == "search_document"

    assert len(resp.vectors) == 2
    assert resp.vectors[0][0] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_embed_cohere_input_type_overridable(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.invoke_responses.append({"embeddings": [[0.1] * 1024], "texts": ["q"]})
    client = BedrockEmbeddingClient(
        model_id=_COHERE, session=fake_session, cohere_input_type="search_query"
    )
    await client.embed(["q"])

    body = _json.loads(fake_bedrock.invoke_calls[0]["body"])
    assert body["input_type"] == "search_query"


# ---- Empty / error paths ----


@pytest.mark.asyncio
async def test_embed_rejects_empty_batch(fake_session: _FakeSession) -> None:
    client = _client(fake_session)
    with pytest.raises(ValueError, match="at least one"):
        await client.embed([])


def _client_error(code: str, status: int = 400) -> ClientError:
    return ClientError(
        error_response={
            "Error": {"Code": code, "Message": "x"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        operation_name="InvokeModel",
    )


@pytest.mark.asyncio
async def test_embed_throttle_maps_to_rate_limit_after_retries(
    fake_bedrock: _FakeBedrockClient,
    fake_session: _FakeSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(retry_mod.asyncio, "sleep", _no_sleep)

    fake_bedrock.invoke_responses.extend([_client_error("ThrottlingException")] * 4)
    client = BedrockEmbeddingClient(model_id=_TITAN, session=fake_session, max_retries=3)
    with pytest.raises(RateLimitError):
        await client.embed(["x"])


@pytest.mark.asyncio
async def test_embed_resource_not_found_is_not_retried(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.invoke_responses.append(_client_error("ResourceNotFoundException", status=404))
    client = _client(fake_session)
    with pytest.raises(ModelNotFoundError):
        await client.embed(["x"])


# ---- close() ----


@pytest.mark.asyncio
async def test_close_releases_client(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.invoke_responses.append({"embedding": [0.0] * 1024, "inputTextTokenCount": 1})
    client = _client(fake_session)
    await client.embed(["x"])
    assert client._client is not None
    await client.close()
    assert client._client is None


# ---- Conformance suite ----


@pytest.mark.asyncio
async def test_passes_embedding_conformance_suite_titan(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    """Conformance suite calls embed(["hello", "world", "agentforge"])
    once after the empty-input check; we script three Titan responses."""
    fake_bedrock.invoke_responses.extend(
        [{"embedding": [0.1] * 1024, "inputTextTokenCount": 1} for _ in range(3)]
    )
    client = _client(fake_session, _TITAN)
    await run_embedding_conformance(client)


@pytest.mark.asyncio
async def test_passes_embedding_conformance_suite_cohere(
    fake_bedrock: _FakeBedrockClient, fake_session: _FakeSession
) -> None:
    fake_bedrock.invoke_responses.append(
        {
            "embeddings": [[0.0] * 1024, [0.0] * 1024, [0.0] * 1024],
            "texts": ["hello", "world", "agentforge"],
        }
    )
    client = _client(fake_session, _COHERE)
    await run_embedding_conformance(client)


# ---- Capability declaration (default) ----


def test_default_capabilities_empty() -> None:
    """Bedrock embedding clients don't declare optional capabilities
    today (no multimodal / matryoshka). Callers still get a working
    `supports()` accessor."""
    client = BedrockEmbeddingClient(model_id=_TITAN)
    assert client.capabilities() == set()
    assert client.supports("multimodal") is False


# ---- enh-004: STS assume-role ----


@pytest.mark.asyncio
async def test_embedding_assume_role_drives_runtime_with_temp_credentials() -> None:
    """When `role_arn` is set, the embedding client assumes the role via STS
    and builds `bedrock-runtime` with the returned temporary credentials."""
    bedrock = _FakeBedrockClient()
    bedrock.invoke_responses.append({"embedding": [0.1] * 1024, "inputTextTokenCount": 3})

    assume_calls: list[dict[str, Any]] = []
    runtime_kwargs: dict[str, Any] = {}

    class _STS:
        async def assume_role(self, **kwargs: Any) -> dict[str, Any]:
            assume_calls.append(kwargs)
            return {
                "Credentials": {
                    "AccessKeyId": "AK-TEMP",
                    "SecretAccessKey": "SK-TEMP",
                    "SessionToken": "TOKEN-TEMP",
                }
            }

    class _Session:
        def client(self, service: str, **kwargs: Any) -> Any:
            target: Any = _STS() if service == "sts" else bedrock
            if service != "sts":
                runtime_kwargs.update(kwargs)

            @asynccontextmanager
            async def _cm() -> AsyncIterator[Any]:
                yield target

            return _cm()

    client = BedrockEmbeddingClient(
        model_id=_TITAN,
        role_arn="arn:aws:iam::123456789012:role/bedrock-embed",
        session=_Session(),
    )
    resp = await client.embed(["hello"])

    assert len(resp.vectors) == 1
    assert assume_calls == [
        {
            "RoleArn": "arn:aws:iam::123456789012:role/bedrock-embed",
            "RoleSessionName": "agentforge",
        }
    ]
    assert runtime_kwargs["aws_session_token"] == "TOKEN-TEMP"
