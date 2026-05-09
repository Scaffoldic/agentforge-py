"""Unit tests for `EmbeddingClient` ABC + `EmbeddingResponse` value type."""

from __future__ import annotations

import pytest
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage
from pydantic import ValidationError


class _FakeEmbedder(EmbeddingClient):
    """Test impl: returns one fixed-dimension vector per text."""

    def __init__(self, *, dim: int = 4) -> None:
        self._dim = dim

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        if not texts:
            raise ValueError("empty batch")
        vectors = tuple(tuple(float(i) for i in range(self._dim)) for _ in texts)
        return EmbeddingResponse(
            vectors=vectors,
            dimensions=self._dim,
            usage=TokenUsage(input_tokens=len(texts) * 4, output_tokens=0),
            cost_usd=0.0001 * len(texts),
            model="fake-embed",
            provider="fake",
        )

    async def close(self) -> None: ...

    def dimensions(self) -> int:
        return self._dim


class _MultimodalEmbedder(_FakeEmbedder):
    def capabilities(self) -> set[str]:
        return {"multimodal"}


# ---- Embed batch happy path ----


@pytest.mark.asyncio
async def test_embed_returns_one_vector_per_input_text() -> None:
    client = _FakeEmbedder(dim=8)
    resp = await client.embed(["hello", "world", "foo"])
    assert len(resp.vectors) == 3
    assert all(len(v) == 8 for v in resp.vectors)
    assert resp.dimensions == 8
    assert resp.model == "fake-embed"


@pytest.mark.asyncio
async def test_embed_rejects_empty_batch() -> None:
    client = _FakeEmbedder()
    with pytest.raises(ValueError, match="empty"):
        await client.embed([])


# ---- Dimensions accessor ----


def test_dimensions_declared_synchronously() -> None:
    """Callers can size storage without a network round-trip."""
    client = _FakeEmbedder(dim=1024)
    assert client.dimensions() == 1024


# ---- EmbeddingResponse validation ----


def test_embedding_response_rejects_negative_cost() -> None:
    with pytest.raises(ValidationError):
        EmbeddingResponse(
            vectors=((0.0,),),
            dimensions=1,
            usage=TokenUsage(input_tokens=1, output_tokens=0),
            cost_usd=-0.01,  # invalid
            model="m",
            provider="p",
        )


def test_embedding_response_rejects_zero_dimensions() -> None:
    with pytest.raises(ValidationError):
        EmbeddingResponse(
            vectors=(),
            dimensions=0,  # min is 1
            usage=TokenUsage(input_tokens=0, output_tokens=0),
            cost_usd=0.0,
            model="m",
            provider="p",
        )


def test_embedding_response_is_frozen() -> None:
    resp = EmbeddingResponse(
        vectors=((1.0, 2.0),),
        dimensions=2,
        usage=TokenUsage(input_tokens=1, output_tokens=0),
        cost_usd=0.0,
        model="m",
        provider="p",
    )
    with pytest.raises(ValidationError):
        resp.cost_usd = 0.5  # type: ignore[misc]


# ---- Capabilities ----


def test_default_embedder_declares_no_capabilities() -> None:
    client = _FakeEmbedder()
    assert client.capabilities() == set()
    assert client.supports("multimodal") is False


def test_multimodal_embedder_declares_capability() -> None:
    client = _MultimodalEmbedder()
    assert client.supports("multimodal") is True
    assert client.supports("matryoshka") is False


# ---- Roundtrip via tuple-of-tuples ----


@pytest.mark.asyncio
async def test_response_vectors_are_immutable() -> None:
    client = _FakeEmbedder(dim=3)
    resp = await client.embed(["a"])
    # vectors is a tuple of tuples, so element-assignment fails
    with pytest.raises(TypeError):
        resp.vectors[0][0] = 99.0  # type: ignore[index]
