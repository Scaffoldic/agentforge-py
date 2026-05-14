"""Unit tests for `VoyageEmbeddingClient`."""

from __future__ import annotations

import pytest
from agentforge_voyage import VoyageEmbeddingClient
from agentforge_voyage._inmem_runner import FakeVoyageRunner


def test_constructor_rejects_empty_model(fake_runner: FakeVoyageRunner) -> None:
    with pytest.raises(ValueError, match="model"):
        VoyageEmbeddingClient(runner=fake_runner, model="")


def test_constructor_rejects_zero_timeout(fake_runner: FakeVoyageRunner) -> None:
    with pytest.raises(ValueError, match="timeout"):
        VoyageEmbeddingClient(runner=fake_runner, model="voyage-3", timeout_seconds=0)


def test_constructor_rejects_invalid_input_type(fake_runner: FakeVoyageRunner) -> None:
    with pytest.raises(ValueError, match="input_type"):
        VoyageEmbeddingClient(runner=fake_runner, model="voyage-3", input_type="passage")


def test_dimensions_default_to_native(fake_runner: FakeVoyageRunner) -> None:
    c = VoyageEmbeddingClient(runner=fake_runner, model="voyage-3-lite")
    assert c.dimensions() == 512


def test_matryoshka_dim_override_supported(fake_runner: FakeVoyageRunner) -> None:
    c = VoyageEmbeddingClient(runner=fake_runner, model="voyage-3-large", dimensions=512)
    assert c.dimensions() == 512
    assert "matryoshka" in c.capabilities()


def test_dim_override_rejected_on_non_matryoshka(fake_runner: FakeVoyageRunner) -> None:
    with pytest.raises(ValueError, match="dimension override"):
        VoyageEmbeddingClient(runner=fake_runner, model="voyage-3-lite", dimensions=256)


def test_dim_override_exceeds_native_rejected(fake_runner: FakeVoyageRunner) -> None:
    with pytest.raises(ValueError, match="exceeds native"):
        VoyageEmbeddingClient(runner=fake_runner, model="voyage-3-large", dimensions=99999)


def test_multimodal_capability_set(fake_runner: FakeVoyageRunner) -> None:
    c = VoyageEmbeddingClient(runner=fake_runner, model="voyage-multimodal-3")
    assert "multimodal" in c.capabilities()


@pytest.mark.asyncio
async def test_embed_rejects_empty(client: VoyageEmbeddingClient) -> None:
    with pytest.raises(ValueError, match="texts"):
        await client.embed([])


@pytest.mark.asyncio
async def test_embed_returns_vectors_at_declared_dim(
    client: VoyageEmbeddingClient,
    fake_runner: FakeVoyageRunner,
) -> None:
    fake_runner.set_response_dim(1024)
    fake_runner.set_response_tokens(20)
    resp = await client.embed(["hello", "world"])
    assert len(resp.vectors) == 2
    assert all(len(v) == 1024 for v in resp.vectors)
    assert resp.usage.input_tokens == 20
    assert resp.cost_usd > 0
    assert resp.provider == "voyage"


@pytest.mark.asyncio
async def test_embed_propagates_dim_override(fake_runner: FakeVoyageRunner) -> None:
    c = VoyageEmbeddingClient(runner=fake_runner, model="voyage-3-large", dimensions=512)
    await c.embed(["x"])
    assert fake_runner.embed_calls[-1].output_dimension == 512


@pytest.mark.asyncio
async def test_embed_propagates_input_type(fake_runner: FakeVoyageRunner) -> None:
    c = VoyageEmbeddingClient(runner=fake_runner, model="voyage-3", input_type="query")
    await c.embed(["x"])
    assert fake_runner.embed_calls[-1].input_type == "query"


@pytest.mark.asyncio
async def test_embed_unknown_model_zero_cost(fake_runner: FakeVoyageRunner) -> None:
    fake_runner.set_response_dim(1024)
    fake_runner.set_response_tokens(50)
    c = VoyageEmbeddingClient(runner=fake_runner, model="voyage-future")
    resp = await c.embed(["hi"])
    assert resp.cost_usd == 0.0


@pytest.mark.asyncio
async def test_close_propagates(
    client: VoyageEmbeddingClient,
    fake_runner: FakeVoyageRunner,
) -> None:
    await client.close()
    assert fake_runner.closed
