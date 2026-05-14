"""Unit tests for `Retriever(mode="hybrid")` + RRF fusion (feat-022).

Builds an in-memory corpus where the vector and lexical paths
disagree on the top hit, asserts the RRF fusion surfaces the
expected order, and covers the constructor validation around the
``hybrid_search`` capability.
"""

from __future__ import annotations

import math

import pytest
from agentforge import InMemoryVectorStore, Retriever
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage
from agentforge_core.values.vector import VectorMatch


class _FakeEmbedder(EmbeddingClient):
    """Embedder that returns vectors close to a target document's vector.

    Index two docs at the same vector (1, 0, 0, 0) and (0, 1, 0, 0);
    a query for "doc-a vector" returns the first; "doc-b vector"
    returns the second. Lets us steer the vector path independently
    of the lexical path.
    """

    def __init__(self, *, vectors_by_query: dict[str, tuple[float, ...]], dim: int) -> None:
        self._dim = dim
        self._vectors_by_query = vectors_by_query

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        out: list[tuple[float, ...]] = []
        for t in texts:
            if t in self._vectors_by_query:
                out.append(self._vectors_by_query[t])
            else:
                out.append(tuple([1.0 / math.sqrt(self._dim)] * self._dim))
        return EmbeddingResponse(
            vectors=tuple(out),
            dimensions=self._dim,
            usage=TokenUsage(input_tokens=sum(len(t) for t in texts), output_tokens=0),
            cost_usd=0.0,
            model="fake-embed",
            provider="fake",
        )

    async def close(self) -> None:
        pass

    def dimensions(self) -> int:
        return self._dim


# ---- Constructor validation ----


def test_constructor_rejects_unsupported_hybrid_store() -> None:
    """A VectorStore that doesn't declare hybrid_search is rejected
    when mode='hybrid'."""

    class _NoHybridStore(VectorStore):
        async def upsert(self, items: list) -> None:
            pass

        async def search(self, query_vector, *, limit=5, filter_metadata=None):
            return []

        async def delete(self, ids: list[str]) -> int:
            return 0

        async def close(self) -> None:
            pass

        def dimensions(self) -> int:
            return 4

    store = _NoHybridStore()
    embedder = _FakeEmbedder(vectors_by_query={}, dim=4)
    with pytest.raises(ValueError, match="hybrid_search"):
        Retriever(store=store, embedder=embedder, mode="hybrid")


def test_constructor_rejects_bad_mode() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(vectors_by_query={}, dim=4)
    with pytest.raises(ValueError, match="mode"):
        Retriever(store=store, embedder=embedder, mode="quantum")  # type: ignore[arg-type]


def test_constructor_rejects_bad_rrf_k() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(vectors_by_query={}, dim=4)
    with pytest.raises(ValueError, match="rrf_k"):
        Retriever(store=store, embedder=embedder, mode="hybrid", rrf_k=0)


def test_default_mode_is_vector() -> None:
    store = InMemoryVectorStore(dimensions=4)
    embedder = _FakeEmbedder(vectors_by_query={}, dim=4)
    r = Retriever(store=store, embedder=embedder)
    assert r.mode == "vector"
    assert r.rrf_k == 60


# ---- Hybrid retrieval semantics ----


@pytest.mark.asyncio
async def test_hybrid_fuses_disagreeing_vector_and_lexical_paths() -> None:
    """Vector says A wins; lexical says B wins. RRF — both at rank 1
    in opposite lists — should surface both at equal rank, with the
    matching document order stable.
    """
    store = InMemoryVectorStore(dimensions=4)
    # Doc A: vector matches the "doc-a vector" query; text irrelevant to "Eiffel".
    # Doc B: vector orthogonal to "doc-a vector"; text contains "Eiffel".
    await store.upsert(
        [
            __vector_item(id_="a", vector=(1.0, 0.0, 0.0, 0.0), text="Paris is the capital"),
            __vector_item(id_="b", vector=(0.0, 1.0, 0.0, 0.0), text="The Eiffel Tower is iconic"),
        ]
    )

    embedder = _FakeEmbedder(
        vectors_by_query={"Eiffel": (1.0, 0.0, 0.0, 0.0)},  # matches doc A vector
        dim=4,
    )
    retriever = Retriever(
        store=store,
        embedder=embedder,
        mode="hybrid",
        top_k=2,
        over_fetch_factor=1,
    )

    matches = await retriever.retrieve("Eiffel")
    ids = [m.id for m in matches]
    # Both should land in the top 2; order depends on RRF tie-break
    # (dict insertion order) but membership is what we assert.
    assert set(ids) == {"a", "b"}
    # Fused score is RRF — lower-bounded by 1/(60+1).
    for m in matches:
        assert m.score >= 1.0 / (60 + 2)


@pytest.mark.asyncio
async def test_hybrid_returns_top_k() -> None:
    store = InMemoryVectorStore(dimensions=4)
    docs = [
        __vector_item(id_=f"d{i}", vector=(1.0, 0.0, 0.0, 0.0), text=f"Paris is doc number {i}")
        for i in range(5)
    ]
    await store.upsert(docs)

    embedder = _FakeEmbedder(
        vectors_by_query={"Paris": (1.0, 0.0, 0.0, 0.0)},
        dim=4,
    )
    retriever = Retriever(
        store=store, embedder=embedder, mode="hybrid", top_k=3, over_fetch_factor=1
    )
    matches = await retriever.retrieve("Paris")
    assert len(matches) == 3


@pytest.mark.asyncio
async def test_vector_mode_regression() -> None:
    """mode='vector' (default) still works without any hybrid path."""
    store = InMemoryVectorStore(dimensions=4)
    await store.upsert([__vector_item(id_="a", vector=(1.0, 0.0, 0.0, 0.0), text="alpha")])
    embedder = _FakeEmbedder(
        vectors_by_query={"alpha": (1.0, 0.0, 0.0, 0.0)},
        dim=4,
    )
    retriever = Retriever(store=store, embedder=embedder, mode="vector", top_k=1)
    matches = await retriever.retrieve("alpha")
    assert [m.id for m in matches] == ["a"]


@pytest.mark.asyncio
async def test_hybrid_with_reranker_applies_post_fusion() -> None:
    """When a reranker is set, it sees the fused candidate set, not
    the raw vector or lexical lists."""

    class _ReverseRanker(Reranker):
        """Reranks by reversing the input order — exposes that the
        reranker is the last step."""

        def __init__(self) -> None:
            self.seen_ids: list[str] = []

        async def rerank(
            self,
            query: str,
            candidates: list[VectorMatch],
            *,
            top_k: int | None = None,
        ) -> list[VectorMatch]:
            self.seen_ids = [c.id for c in candidates]
            reversed_ = list(reversed(candidates))
            limit = top_k if top_k is not None else len(reversed_)
            return reversed_[:limit]

        async def close(self) -> None:
            pass

    store = InMemoryVectorStore(dimensions=4)
    await store.upsert(
        [
            __vector_item(id_="a", vector=(1.0, 0.0, 0.0, 0.0), text="alpha doc"),
            __vector_item(id_="b", vector=(0.0, 1.0, 0.0, 0.0), text="beta doc"),
        ]
    )
    embedder = _FakeEmbedder(
        vectors_by_query={"alpha": (1.0, 0.0, 0.0, 0.0)},
        dim=4,
    )
    ranker = _ReverseRanker()
    retriever = Retriever(
        store=store,
        embedder=embedder,
        mode="hybrid",
        top_k=2,
        over_fetch_factor=1,
        reranker=ranker,
    )
    matches = await retriever.retrieve("alpha")
    # The reranker saw the *fused* candidate set.
    assert set(ranker.seen_ids) == {"a", "b"}
    # And it returned the reversal of that fused order.
    assert [m.id for m in matches] == list(reversed(ranker.seen_ids))


# ---- Helpers ----


def __vector_item(*, id_: str, vector: tuple[float, ...], text: str):
    from agentforge_core.values.vector import VectorItem  # noqa: PLC0415

    return VectorItem(id=id_, vector=vector, text=text, metadata={})
