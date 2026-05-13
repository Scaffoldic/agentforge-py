"""Unit tests for `Retriever` + `Reranker` integration (feat-021)."""

from __future__ import annotations

import math

import pytest
from agentforge import InMemoryVectorStore, Retriever
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage
from agentforge_core.values.vector import VectorMatch


class _FakeEmbedder(EmbeddingClient):
    """Deterministic per-text embedder so the rerank tests can predict
    which candidates the underlying vector store returns."""

    def __init__(self, *, dim: int = 4) -> None:
        self._dim = dim
        self.closed = False

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        if not texts:
            msg = "embed() requires at least one text"
            raise ValueError(msg)
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
    raw = [0.01] * dim
    for i, ch in enumerate(text):
        raw[i % dim] += ord(ch)
    norm = math.sqrt(sum(x * x for x in raw))
    return tuple(x / norm for x in raw) if norm > 0 else tuple(raw)


class _RecordingReranker(Reranker):
    """Reranker that reverses the input order + records its calls so
    the test can assert how the retriever invoked it."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int | None]] = []
        self.closed = False

    async def rerank(
        self,
        query: str,
        candidates: list[VectorMatch],
        *,
        top_k: int | None = None,
    ) -> list[VectorMatch]:
        if top_k is not None and top_k < 1:
            msg = f"top_k must be >= 1, got {top_k}"
            raise ValueError(msg)
        self.calls.append((query, len(candidates), top_k))
        reversed_ = list(reversed(candidates))
        n = len(reversed_)
        rescored = [
            VectorMatch(
                id=m.id,
                text=m.text,
                metadata=m.metadata,
                score=(n - i) / n if n else 0.0,
            )
            for i, m in enumerate(reversed_)
        ]
        if top_k is not None:
            return rescored[:top_k]
        return rescored

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def populated_retriever_no_reranker() -> Retriever:
    """A retriever with five indexed documents; vector top-5 in
    descending score determines the canonical order."""
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    return Retriever(store=store, embedder=embedder, top_k=3)


# ---- constructor validation ----


def test_over_fetch_factor_rejects_zero() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    with pytest.raises(ValueError, match="over_fetch_factor"):
        Retriever(store=store, embedder=embedder, over_fetch_factor=0)


def test_reranker_property_exposes_injected_instance() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    rer = _RecordingReranker()
    retriever = Retriever(store=store, embedder=embedder, reranker=rer)
    assert retriever.reranker is rer

    no_rer = Retriever(store=store, embedder=embedder)
    assert no_rer.reranker is None


# ---- retrieve with reranker ----


@pytest.mark.asyncio
async def test_retrieve_pulls_overfetch_and_reranks_to_top_k() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    rer = _RecordingReranker()
    retriever = Retriever(
        store=store,
        embedder=embedder,
        reranker=rer,
        top_k=2,
        over_fetch_factor=3,
    )
    await retriever.add_documents(["alpha", "beta", "gamma", "delta", "epsilon", "zeta"])

    results = await retriever.retrieve("alpha", top_k=2)

    # Reranker invoked once with the query, the over-fetch pool, and
    # the requested top_k.
    assert len(rer.calls) == 1
    query, n_candidates, requested_top_k = rer.calls[0]
    assert query == "alpha"
    assert n_candidates == 6  # 2 * 3 over-fetch
    assert requested_top_k == 2
    assert len(results) == 2


@pytest.mark.asyncio
async def test_retrieve_without_reranker_skips_over_fetch() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(
        store=store,
        embedder=embedder,
        top_k=2,
        over_fetch_factor=10,  # ignored when reranker is None
    )
    await retriever.add_documents(["alpha", "beta", "gamma"])

    results = await retriever.retrieve("alpha", top_k=2)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_retrieve_with_over_fetch_factor_one_still_invokes_reranker() -> None:
    """`over_fetch_factor=1` disables over-fetch but still routes
    through the reranker — useful when callers want the reranker's
    score normalisation without paying for over-fetch."""
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    rer = _RecordingReranker()
    retriever = Retriever(
        store=store,
        embedder=embedder,
        reranker=rer,
        top_k=3,
        over_fetch_factor=1,
    )
    await retriever.add_documents(["alpha", "beta", "gamma", "delta"])

    await retriever.retrieve("alpha", top_k=3)

    _, n_candidates, _ = rer.calls[0]
    assert n_candidates == 3  # top_k, not over-fetched


@pytest.mark.asyncio
async def test_close_propagates_to_reranker() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    rer = _RecordingReranker()
    retriever = Retriever(store=store, embedder=embedder, reranker=rer)
    await retriever.close()
    assert rer.closed is True


@pytest.mark.asyncio
async def test_close_handles_missing_reranker() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(store=store, embedder=embedder)
    await retriever.close()  # must not raise
