"""Unit tests for `OllamaEmbeddingClient`."""

from __future__ import annotations

import pytest
from agentforge_ollama import OllamaEmbeddingClient
from agentforge_ollama._inmem_runner import FakeOllamaRunner


def test_constructor_rejects_empty_model(fake_runner: FakeOllamaRunner) -> None:
    with pytest.raises(ValueError, match="model"):
        OllamaEmbeddingClient(runner=fake_runner, model="", dimensions=1024)


def test_constructor_rejects_zero_dimensions(fake_runner: FakeOllamaRunner) -> None:
    with pytest.raises(ValueError, match="dimensions"):
        OllamaEmbeddingClient(runner=fake_runner, model="m", dimensions=0)


def test_constructor_rejects_zero_timeout(fake_runner: FakeOllamaRunner) -> None:
    with pytest.raises(ValueError, match="timeout"):
        OllamaEmbeddingClient(
            runner=fake_runner,
            model="m",
            dimensions=1024,
            timeout_seconds=0,
        )


def test_dimensions_accessor(embedding_client: OllamaEmbeddingClient) -> None:
    assert embedding_client.dimensions() == 1024


@pytest.mark.asyncio
async def test_embed_rejects_empty(embedding_client: OllamaEmbeddingClient) -> None:
    with pytest.raises(ValueError, match="texts"):
        await embedding_client.embed([])


@pytest.mark.asyncio
async def test_embed_returns_vectors_with_zero_cost(
    embedding_client: OllamaEmbeddingClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    fake_runner.set_embedding_dim(1024)
    resp = await embedding_client.embed(["hello", "world"])
    assert len(resp.vectors) == 2
    assert all(len(v) == 1024 for v in resp.vectors)
    assert resp.cost_usd == 0.0
    assert resp.provider == "ollama"


@pytest.mark.asyncio
async def test_embed_dimension_mismatch_raises(
    embedding_client: OllamaEmbeddingClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    fake_runner.set_embedding_response(
        {
            "model": "mxbai-embed-large",
            "embeddings": [[0.0, 0.1, 0.2]],  # 3-dim, expected 1024.
            "prompt_eval_count": 1,
        },
    )
    with pytest.raises(ValueError, match="dimensionality"):
        await embedding_client.embed(["x"])


@pytest.mark.asyncio
async def test_close_propagates(
    embedding_client: OllamaEmbeddingClient,
    fake_runner: FakeOllamaRunner,
) -> None:
    await embedding_client.close()
    assert fake_runner.closed
