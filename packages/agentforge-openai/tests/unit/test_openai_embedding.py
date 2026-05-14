"""Unit tests for `OpenAIEmbeddingClient`."""

from __future__ import annotations

import pytest
from agentforge_openai import OpenAIEmbeddingClient
from agentforge_openai._inmem_runner import FakeOpenAIRunner
from agentforge_openai._pricing import embedding_cost_usd


def test_constructor_rejects_empty_model(fake_runner: FakeOpenAIRunner) -> None:
    with pytest.raises(ValueError, match="model"):
        OpenAIEmbeddingClient(runner=fake_runner, model="")


def test_constructor_rejects_zero_timeout(fake_runner: FakeOpenAIRunner) -> None:
    with pytest.raises(ValueError, match="timeout"):
        OpenAIEmbeddingClient(
            runner=fake_runner,
            model="text-embedding-3-small",
            timeout_seconds=0,
        )


def test_dimensions_default_to_native(fake_runner: FakeOpenAIRunner) -> None:
    c = OpenAIEmbeddingClient(runner=fake_runner, model="text-embedding-3-small")
    assert c.dimensions() == 1536


def test_dimensions_override_supported_on_matryoshka(fake_runner: FakeOpenAIRunner) -> None:
    c = OpenAIEmbeddingClient(
        runner=fake_runner,
        model="text-embedding-3-large",
        dimensions=512,
    )
    assert c.dimensions() == 512
    assert "matryoshka" in c.capabilities()


def test_dimensions_override_rejected_on_ada(fake_runner: FakeOpenAIRunner) -> None:
    with pytest.raises(ValueError, match="Matryoshka"):
        OpenAIEmbeddingClient(
            runner=fake_runner,
            model="text-embedding-ada-002",
            dimensions=512,
        )


def test_dimensions_override_rejected_when_exceeds_native(
    fake_runner: FakeOpenAIRunner,
) -> None:
    with pytest.raises(ValueError, match="exceeds native"):
        OpenAIEmbeddingClient(
            runner=fake_runner,
            model="text-embedding-3-small",
            dimensions=99999,
        )


def test_dimensions_override_rejects_zero(fake_runner: FakeOpenAIRunner) -> None:
    with pytest.raises(ValueError, match="dimensions"):
        OpenAIEmbeddingClient(
            runner=fake_runner,
            model="text-embedding-3-small",
            dimensions=0,
        )


@pytest.mark.asyncio
async def test_embed_rejects_empty_input(embedding_client: OpenAIEmbeddingClient) -> None:
    with pytest.raises(ValueError, match="texts"):
        await embedding_client.embed([])


@pytest.mark.asyncio
async def test_embed_returns_vectors_and_cost(
    embedding_client: OpenAIEmbeddingClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    # Fake returns zero-vectors of declared dims; assert shape + cost.
    fake_runner.set_embedding_dims(1536)
    resp = await embedding_client.embed(["hello", "world"])
    assert len(resp.vectors) == 2
    assert all(len(v) == 1536 for v in resp.vectors)
    assert resp.dimensions == 1536
    assert resp.provider == "openai"


@pytest.mark.asyncio
async def test_embed_propagates_dimensions_arg_to_runner_only_when_overridden(
    fake_runner: FakeOpenAIRunner,
) -> None:
    # Native dims = no override sent.
    c1 = OpenAIEmbeddingClient(runner=fake_runner, model="text-embedding-3-small")
    await c1.embed(["x"])
    assert fake_runner.embedding_calls[-1].dimensions is None

    # Overridden dims = sent to runner.
    fake_runner.set_embedding_dims(512)
    c2 = OpenAIEmbeddingClient(
        runner=fake_runner,
        model="text-embedding-3-small",
        dimensions=512,
    )
    await c2.embed(["x"])
    assert fake_runner.embedding_calls[-1].dimensions == 512


@pytest.mark.asyncio
async def test_embed_dimension_mismatch_raises(
    fake_runner: FakeOpenAIRunner,
) -> None:
    # Override runner response to return wrong dimensionality.
    fake_runner.set_embedding_response(
        {
            "model": "text-embedding-3-small",
            "data": [{"index": 0, "embedding": [0.0, 0.1]}],  # 2-dim, expected 1536
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        },
    )
    c = OpenAIEmbeddingClient(runner=fake_runner, model="text-embedding-3-small")
    with pytest.raises(ValueError, match="dimensionality"):
        await c.embed(["x"])


def test_embedding_cost_known_model() -> None:
    assert embedding_cost_usd("text-embedding-3-small", input_tokens=1_000_000) > 0.0


def test_embedding_cost_unknown_model_zero() -> None:
    assert embedding_cost_usd("unknown-embedder", input_tokens=1_000) == 0.0


@pytest.mark.asyncio
async def test_close_propagates(
    embedding_client: OpenAIEmbeddingClient,
    fake_runner: FakeOpenAIRunner,
) -> None:
    await embedding_client.close()
    assert fake_runner.closed
