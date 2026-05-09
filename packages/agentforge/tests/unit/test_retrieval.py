"""Unit tests for the `Retriever` adapter."""

from __future__ import annotations

import math

import pytest
from agentforge import InMemoryVectorStore, Retriever
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage


class _FakeEmbedder(EmbeddingClient):
    """Deterministic per-text embedder for tests.

    Maps each input text to a fixed vector via a simple hash. Same
    text always yields the same vector, so retrieve() can find an
    exact match against an indexed document.
    """

    def __init__(self, *, dim: int = 4) -> None:
        self._dim = dim
        self.embed_calls: list[list[str]] = []
        self.closed = False

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        if not texts:
            raise ValueError("embed() requires at least one text")
        self.embed_calls.append(list(texts))
        vectors = tuple(_text_to_vector(t, self._dim) for t in texts)
        return EmbeddingResponse(
            vectors=vectors,
            dimensions=self._dim,
            usage=TokenUsage(input_tokens=sum(len(t) for t in texts), output_tokens=0),
            cost_usd=0.0,
            model="fake-embed",
            provider="fake",
        )

    async def close(self) -> None:
        self.closed = True

    def dimensions(self) -> int:
        return self._dim


def _text_to_vector(text: str, dim: int) -> tuple[float, ...]:
    """Stable text → vector using char codes, L2-normalised."""
    raw = [0.01] * dim
    for i, ch in enumerate(text):
        raw[i % dim] += ord(ch)
    norm = math.sqrt(sum(x * x for x in raw))
    return tuple(x / norm for x in raw) if norm > 0 else tuple(raw)


# ---- Constructor validation ----


def test_constructor_rejects_zero_top_k() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    with pytest.raises(ValueError, match="top_k"):
        Retriever(store=store, embedder=embedder, top_k=0)


def test_constructor_rejects_zero_batch_size() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    with pytest.raises(ValueError, match="batch_size"):
        Retriever(store=store, embedder=embedder, batch_size=0)


def test_constructor_rejects_dimension_mismatch() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=8)
    with pytest.raises(ValueError, match="dimensions"):
        Retriever(store=store, embedder=embedder)


def test_store_and_embedder_accessors_round_trip() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)
    assert retriever.store is store
    assert retriever.embedder is embedder


# ---- add_documents ----


@pytest.mark.asyncio
async def test_add_documents_returns_generated_ulids_when_ids_omitted() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)

    ids = await retriever.add_documents(["alpha", "beta", "gamma"])
    assert len(ids) == 3
    # ULIDs are 26 chars; uniqueness comes for free.
    assert all(len(i) == 26 for i in ids)
    assert len(set(ids)) == 3


@pytest.mark.asyncio
async def test_add_documents_uses_caller_supplied_ids() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)

    ids = await retriever.add_documents(["alpha", "beta"], ids=["doc-a", "doc-b"])
    assert ids == ["doc-a", "doc-b"]


@pytest.mark.asyncio
async def test_add_documents_attaches_metadata() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)

    await retriever.add_documents(
        ["alpha", "beta"],
        ids=["a", "b"],
        metadata=[{"category": "doc"}, {"category": "note"}],
    )
    matches = await retriever.retrieve("alpha", top_k=10)
    by_id = {m.id: m for m in matches}
    assert by_id["a"].metadata == {"category": "doc"}
    assert by_id["b"].metadata == {"category": "note"}


@pytest.mark.asyncio
async def test_add_documents_empty_list_is_no_op() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)
    ids = await retriever.add_documents([])
    assert ids == []
    # Embedder was never called.
    assert embedder.embed_calls == []


@pytest.mark.asyncio
async def test_add_documents_rejects_id_length_mismatch() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)
    with pytest.raises(ValueError, match="ids"):
        await retriever.add_documents(["a", "b"], ids=["only-one"])


@pytest.mark.asyncio
async def test_add_documents_rejects_metadata_length_mismatch() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)
    with pytest.raises(ValueError, match="metadata"):
        await retriever.add_documents(["a", "b"], metadata=[{"k": "v"}])


@pytest.mark.asyncio
async def test_add_documents_batches_at_batch_size() -> None:
    """5 texts with batch_size=2 -> 3 embedder calls (2, 2, 1)."""
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder, batch_size=2)

    await retriever.add_documents([f"text-{i}" for i in range(5)])
    sizes = [len(call) for call in embedder.embed_calls]
    assert sizes == [2, 2, 1]


# ---- retrieve ----


@pytest.mark.asyncio
async def test_retrieve_top_hit_is_exact_match() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)

    await retriever.add_documents(
        ["paris is the capital of france", "the louvre is in paris"],
        ids=["d1", "d2"],
    )
    matches = await retriever.retrieve("paris is the capital of france", top_k=2)
    assert matches[0].id == "d1"
    assert matches[0].score == pytest.approx(1.0, abs=1e-6)


@pytest.mark.asyncio
async def test_retrieve_uses_constructor_top_k_when_kwarg_omitted() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder, top_k=2)

    await retriever.add_documents([f"text-{i}" for i in range(5)])
    matches = await retriever.retrieve("text-0")
    assert len(matches) == 2


@pytest.mark.asyncio
async def test_retrieve_top_k_kwarg_overrides_default() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder, top_k=2)

    await retriever.add_documents([f"text-{i}" for i in range(5)])
    matches = await retriever.retrieve("text-0", top_k=4)
    assert len(matches) == 4


@pytest.mark.asyncio
async def test_retrieve_rejects_zero_top_k_kwarg() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)
    with pytest.raises(ValueError, match="top_k"):
        await retriever.retrieve("query", top_k=0)


@pytest.mark.asyncio
async def test_retrieve_forwards_metadata_filter() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder, top_k=10)

    await retriever.add_documents(
        ["alpha doc", "alpha note", "beta doc"],
        ids=["1", "2", "3"],
        metadata=[
            {"category": "doc"},
            {"category": "note"},
            {"category": "doc"},
        ],
    )
    matches = await retriever.retrieve("alpha", filter_metadata={"category": "doc"})
    ids = sorted(m.id for m in matches)
    assert ids == ["1", "3"]


# ---- close() ----


@pytest.mark.asyncio
async def test_close_propagates_to_store_and_embedder() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)

    await retriever.add_documents(["x"])
    await retriever.close()
    # Store cleared
    assert await store.search(_text_to_vector("x", 4), limit=10) == []
    # Embedder marked closed
    assert embedder.closed is True
