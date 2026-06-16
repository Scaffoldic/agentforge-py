"""`BedrockEmbeddingClient` — `EmbeddingClient` over Bedrock InvokeModel.

Bedrock's embedding APIs (Titan, Cohere) use `InvokeModel`, not the
Converse API. The two model families have different request/response
shapes:

  - Titan Text Embeddings V1/V2: `{"inputText": "..."}` per call.
    Returns `{"embedding": [...], "inputTextTokenCount": N}`. Single
    text per request — we loop over batched inputs in the driver.
  - Cohere Embed v3 (English / multilingual): `{"texts": [...],
    "input_type": "search_document"}`. Returns
    `{"embeddings": [[...], ...], "texts": [...]}` natively batched.

The driver detects the family from the model id and dispatches.
Cross-region inference profiles are NOT supported for embedding
models (per AWS docs); model ids must be region-pinned.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import aioboto3
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.resolver import register_embedding_provider
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage
from botocore.exceptions import ClientError

from agentforge_bedrock._errors import map_client_error, map_unexpected
from agentforge_bedrock._pricing import compute_cost_usd, lookup
from agentforge_bedrock._retry import with_retry

log = logging.getLogger(__name__)

_PROVIDER_NAME = "bedrock"
_DEFAULT_REGION = "us-east-1"
_DEFAULT_TIMEOUT_SECONDS = 60.0
_DEFAULT_MAX_RETRIES = 3

# Default vector dimensionality if the model is not in the price
# table. Conservative choice — Titan v2's default is 1024.
_FALLBACK_DIMENSIONS = 1024


@register_embedding_provider("bedrock")
class BedrockEmbeddingClient(EmbeddingClient):
    """`EmbeddingClient` over AWS Bedrock InvokeModel.

    Args:
        model_id: Bedrock embedding model id, e.g.
            `amazon.titan-embed-text-v2:0`,
            `cohere.embed-english-v3`,
            `cohere.embed-multilingual-v3`.
        region: AWS region. Embedding models do not support
            cross-region inference profiles; the request is
            region-pinned. Defaults to AWS_REGION env or us-east-1.
        max_retries: Retries on retryable errors. Default 3.
        timeout_seconds: Per-request timeout. Default 60s.
        aws_profile: Optional named profile from `~/.aws/credentials`.
        cohere_input_type: For Cohere models, the embedding intent
            (`search_document` / `search_query` / `classification` /
            `clustering`). Default `"search_document"` — appropriate
            for storing vectors that will be queried later.
        session: Optional injected aioboto3.Session for tests.
    """

    def __init__(
        self,
        *,
        model_id: str,
        region: str | None = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        aws_profile: str | None = None,
        role_arn: str | None = None,
        role_session_name: str = "agentforge",
        cohere_input_type: str = "search_document",
        session: Any | None = None,
    ) -> None:
        if not model_id:
            raise ValueError("model_id must be a non-empty string")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._model_id = model_id
        self._region = region or _resolve_region()
        self._max_retries = max_retries
        self._timeout_seconds = timeout_seconds
        self._aws_profile = aws_profile
        self._role_arn = role_arn
        self._role_session_name = role_session_name
        self._cohere_input_type = cohere_input_type
        self._session: Any | None = session
        self._client_cm: Any | None = None
        self._client: Any | None = None

        # Resolve dimensions up-front from the price table so callers
        # can size storage without a network round-trip.
        price = lookup(model_id)
        self._dimensions = (
            price.dimensions
            if price is not None and price.dimensions is not None
            else _FALLBACK_DIMENSIONS
        )

    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        if not texts:
            raise ValueError("embed() requires at least one input text")
        client = await self._ensure_client()
        family = _detect_family(self._model_id)

        if family == "cohere":
            vectors, input_tokens = await self._embed_cohere(client, texts)
        else:
            vectors, input_tokens = await self._embed_titan(client, texts)

        return EmbeddingResponse(
            vectors=tuple(tuple(v) for v in vectors),
            dimensions=self._dimensions,
            usage=TokenUsage(input_tokens=input_tokens, output_tokens=0),
            cost_usd=compute_cost_usd(self._model_id, input_tokens=input_tokens),
            model=self._model_id,
            provider=_PROVIDER_NAME,
        )

    async def close(self) -> None:
        if self._client_cm is not None:
            try:
                await self._client_cm.__aexit__(None, None, None)
            finally:
                self._client_cm = None
                self._client = None

    # ------------------------------------------------------------------
    # Internal — per-family request shapes
    # ------------------------------------------------------------------

    async def _embed_titan(self, client: Any, texts: list[str]) -> tuple[list[list[float]], int]:
        """Titan accepts ONE text per call — loop and accumulate."""
        vectors: list[list[float]] = []
        total_tokens = 0
        for text in texts:
            body = json.dumps({"inputText": text})
            response_body = await self._invoke(client, body)
            vectors.append([float(x) for x in response_body.get("embedding", [])])
            total_tokens += int(response_body.get("inputTextTokenCount", 0))
        return vectors, total_tokens

    async def _embed_cohere(self, client: Any, texts: list[str]) -> tuple[list[list[float]], int]:
        """Cohere supports a native batch — one InvokeModel call."""
        body = json.dumps(
            {
                "texts": texts,
                "input_type": self._cohere_input_type,
            }
        )
        response_body = await self._invoke(client, body)
        raw_vectors = response_body.get("embeddings", []) or []
        vectors = [[float(x) for x in v] for v in raw_vectors]
        # Cohere doesn't return token counts; estimate as ~chars/4 per
        # text. Used only for cost reporting and rough budget tracking.
        total_tokens = sum(max(1, len(t) // 4) for t in texts)
        return vectors, total_tokens

    async def _invoke(self, client: Any, body: str) -> dict[str, Any]:
        """Issue one InvokeModel call with retry + error mapping."""

        async def _do() -> dict[str, Any]:
            try:
                response = await asyncio.wait_for(
                    client.invoke_model(
                        modelId=self._model_id,
                        body=body,
                        accept="application/json",
                        contentType="application/json",
                    ),
                    timeout=self._timeout_seconds,
                )
            except TimeoutError as exc:
                raise map_unexpected(exc) from exc
            except ClientError as exc:
                raise map_client_error(exc) from exc
            except Exception as exc:
                raise map_unexpected(exc) from exc
            payload = await _read_body(response["body"])
            parsed: dict[str, Any] = json.loads(payload)
            return parsed

        return await with_retry(_do, max_retries=self._max_retries)

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if self._session is None:
            self._session = aioboto3.Session(profile_name=self._aws_profile)
        creds = await self._assume_role_credentials() if self._role_arn else {}
        self._client_cm = self._session.client("bedrock-runtime", region_name=self._region, **creds)
        self._client = await self._client_cm.__aenter__()
        return self._client

    async def _assume_role_credentials(self) -> dict[str, str]:
        """Assume `role_arn` via STS and return temporary credential
        kwargs for the `bedrock-runtime` client (enh-004)."""
        assert self._session is not None
        async with self._session.client("sts", region_name=self._region) as sts:
            resp = await sts.assume_role(
                RoleArn=self._role_arn,
                RoleSessionName=self._role_session_name,
            )
        creds = resp["Credentials"]
        return {
            "aws_access_key_id": creds["AccessKeyId"],
            "aws_secret_access_key": creds["SecretAccessKey"],
            "aws_session_token": creds["SessionToken"],
        }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


async def _read_body(body: Any) -> bytes:
    """aioboto3 responses' `body` is a `StreamingBody`-alike async
    object with a `.read()` coroutine. Tests can pass plain bytes or
    a sync object exposing `.read()`."""
    read = getattr(body, "read", None)
    if read is None:
        return bytes(body)
    result = read()
    if hasattr(result, "__await__"):
        awaited: bytes = await result
        return awaited
    return bytes(result)


def _detect_family(model_id: str) -> str:
    """Return `"cohere"` or `"titan"` based on the model id prefix.

    Unknown models default to titan since both Titan v1 and v2 use the
    simpler `inputText` shape; Cohere is a clear opt-in via prefix.
    """
    if model_id.startswith("cohere."):
        return "cohere"
    return "titan"


def _resolve_region() -> str:
    return os.environ.get("AWS_REGION") or _DEFAULT_REGION


__all__ = ["BedrockEmbeddingClient"]
