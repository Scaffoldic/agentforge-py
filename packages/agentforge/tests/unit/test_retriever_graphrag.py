"""Unit tests for `Retriever(graph_expansion=...)` (feat-023).

Covers `GraphExpansion` value validation, single- + multi-hop
expansion, edge-type filtering, score decay, dedup between
direct hits and expansion nodes, missing-graph-node tolerance,
reranker post-expansion, and composition with hybrid mode.
"""

from __future__ import annotations

import math

import pytest
from agentforge import InMemoryGraphStore, InMemoryVectorStore, Retriever
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.values.graph import GraphEdge, GraphNode
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage
from agentforge_core.values.retrieval import GraphExpansion
from agentforge_core.values.vector import VectorItem, VectorMatch

# ---------- Fixtures ----------


class _FakeEmbedder(EmbeddingClient):
    """Returns deterministic per-text vectors via a simple hash."""

    def __init__(self, *, dim: int = 4) -> None:
        self._dim = dim

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        vectors = tuple(_text_to_vector(t, self._dim) for t in texts)
        return EmbeddingResponse(
            vectors=vectors,
            dimensions=self._dim,
            usage=TokenUsage(input_tokens=sum(len(t) for t in texts), output_tokens=0),
            cost_usd=0.0,
            model="fake",
            provider="fake",
        )

    async def close(self) -> None:
        pass

    def dimensions(self) -> int:
        return self._dim


def _text_to_vector(text: str, dim: int) -> tuple[float, ...]:
    raw = [0.01] * dim
    for i, ch in enumerate(text):
        raw[i % dim] += ord(ch)
    norm = math.sqrt(sum(x * x for x in raw))
    return tuple(x / norm for x in raw) if norm > 0 else tuple(raw)


async def _seeded_stores(
    *,
    docs: dict[str, str],
    edges: list[tuple[str, str, str]],
) -> tuple[InMemoryVectorStore, InMemoryGraphStore]:
    """Populate a vector store + graph store with aligned ids."""
    vec_store = InMemoryVectorStore(dimensions=4)
    items = [
        VectorItem(id=doc_id, vector=_text_to_vector(text, 4), text=text, metadata={})
        for doc_id, text in docs.items()
    ]
    await vec_store.upsert(items)

    graph_store = InMemoryGraphStore()
    for doc_id, text in docs.items():
        await graph_store.add_node(GraphNode(id=doc_id, labels=("Doc",), properties={"text": text}))
    for src, dst, edge_type in edges:
        await graph_store.add_edge(GraphEdge(src=src, dst=dst, edge_type=edge_type))
    return vec_store, graph_store


# ---------- GraphExpansion value validation ----------


def test_graph_expansion_rejects_max_hops_zero() -> None:
    graph_store = InMemoryGraphStore()
    with pytest.raises(ValueError, match="max_hops"):
        GraphExpansion(store=graph_store, max_hops=0)


def test_graph_expansion_rejects_decay_zero() -> None:
    graph_store = InMemoryGraphStore()
    with pytest.raises(ValueError, match="decay"):
        GraphExpansion(store=graph_store, decay=0.0)


def test_graph_expansion_rejects_decay_above_one() -> None:
    graph_store = InMemoryGraphStore()
    with pytest.raises(ValueError, match="decay"):
        GraphExpansion(store=graph_store, decay=1.5)


# ---------- Expansion semantics ----------


@pytest.mark.asyncio
async def test_single_hop_expansion_adds_one_neighbour() -> None:
    """Vector seed=[a]; with max_hops=1, graph adds b (a→CITES→b)."""
    vec_store, graph_store = await _seeded_stores(
        docs={"a": "alpha", "b": "beta", "c": "gamma"},
        edges=[("a", "b", "CITES"), ("b", "c", "CITES")],
    )
    embedder = _FakeEmbedder(dim=4)
    # top_k=1 → vector seed is just `a`. Expansion appends `b` after.
    retriever = Retriever(
        store=vec_store,
        embedder=embedder,
        top_k=1,
        over_fetch_factor=1,
        graph_expansion=GraphExpansion(store=graph_store, max_hops=1, decay=0.5),
    )
    results = await retriever.retrieve("alpha")
    ids = [m.id for m in results]
    # `a` is the direct seed; `b` arrives via 1-hop expansion.
    assert ids == ["a", "b"]


@pytest.mark.asyncio
async def test_multi_hop_expansion_collects_2_hop_neighbours() -> None:
    """max_hops=2 with a single vector seed returns [a, b, c]."""
    vec_store, graph_store = await _seeded_stores(
        docs={"a": "alpha", "b": "beta", "c": "gamma"},
        edges=[("a", "b", "CITES"), ("b", "c", "CITES")],
    )
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(
        store=vec_store,
        embedder=embedder,
        top_k=1,
        over_fetch_factor=1,
        graph_expansion=GraphExpansion(store=graph_store, max_hops=2, decay=0.5),
    )
    results = await retriever.retrieve("alpha")
    ids = [m.id for m in results]
    # a is the direct vector hit; b and c arrive via graph expansion.
    assert "a" in ids
    assert "b" in ids
    assert "c" in ids


@pytest.mark.asyncio
async def test_edge_type_filtering_excludes_other_types() -> None:
    """edge_types=('CITES',) skips b→AUTHORED_BY→c expansion."""
    vec_store, graph_store = await _seeded_stores(
        docs={"a": "alpha", "b": "beta", "c": "gamma"},
        edges=[("a", "b", "CITES"), ("b", "c", "AUTHORED_BY")],
    )
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(
        store=vec_store,
        embedder=embedder,
        top_k=1,
        over_fetch_factor=1,
        graph_expansion=GraphExpansion(
            store=graph_store, max_hops=2, edge_types=("CITES",), decay=0.5
        ),
    )
    results = await retriever.retrieve("alpha")
    ids = [m.id for m in results]
    assert "a" in ids
    assert "b" in ids
    # c is only reachable via AUTHORED_BY → filtered out.
    assert "c" not in ids


@pytest.mark.asyncio
async def test_score_decay_applies_per_hop() -> None:
    """Expansion node at depth d has score seed.score * decay**d."""
    vec_store, graph_store = await _seeded_stores(
        docs={"a": "alpha", "b": "beta", "c": "gamma"},
        edges=[("a", "b", "CITES"), ("b", "c", "CITES")],
    )
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(
        store=vec_store,
        embedder=embedder,
        top_k=1,
        over_fetch_factor=1,
        graph_expansion=GraphExpansion(store=graph_store, max_hops=2, decay=0.5),
    )
    results = await retriever.retrieve("alpha")
    by_id = {m.id: m for m in results}
    seed = by_id["a"]
    # depth-1 neighbour gets half the seed's score.
    assert by_id["b"].score == pytest.approx(seed.score * 0.5)
    # depth-2 neighbour gets a quarter.
    assert by_id["c"].score == pytest.approx(seed.score * 0.25)
    # Expansion metadata carries provenance.
    assert by_id["b"].metadata["agentforge.expanded_from"] == "a"
    assert by_id["b"].metadata["agentforge.hop"] == 1
    assert by_id["c"].metadata["agentforge.hop"] == 2


@pytest.mark.asyncio
async def test_dedup_direct_hit_wins_over_expansion() -> None:
    """When a vector hit and an expansion node share an id, the
    direct hit wins (its score is higher and order is preserved)."""
    vec_store, graph_store = await _seeded_stores(
        docs={"a": "alpha", "b": "beta"},
        edges=[("a", "b", "CITES")],
    )
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(
        store=vec_store,
        embedder=embedder,
        top_k=2,
        over_fetch_factor=2,  # over-fetch so vector pulls both a + b
        graph_expansion=GraphExpansion(store=graph_store, max_hops=1, decay=0.5),
    )
    results = await retriever.retrieve("alpha")
    # `b` should appear exactly once even though it's both a vector
    # hit and a 1-hop neighbour of `a`.
    ids = [m.id for m in results]
    assert ids.count("b") == 1
    # The remaining `b` should have its original vector score, not the
    # decayed expansion score — direct hits win.
    b_match = next(m for m in results if m.id == "b")
    assert "agentforge.expanded_from" not in b_match.metadata


@pytest.mark.asyncio
async def test_missing_graph_node_is_silently_skipped() -> None:
    """Vector hit with no corresponding graph node yields no
    expansion for that seed (no exception)."""
    vec_store = InMemoryVectorStore(dimensions=4)
    await vec_store.upsert(
        [VectorItem(id="orphan", vector=_text_to_vector("orphan", 4), text="orphan")]
    )
    graph_store = InMemoryGraphStore()  # empty
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(
        store=vec_store,
        embedder=embedder,
        top_k=1,
        over_fetch_factor=1,
        graph_expansion=GraphExpansion(store=graph_store, max_hops=2, decay=0.5),
    )
    results = await retriever.retrieve("orphan")
    assert [m.id for m in results] == ["orphan"]


# ---------- Reranker layering ----------


@pytest.mark.asyncio
async def test_reranker_sees_expanded_candidate_set() -> None:
    """The reranker (when set) is applied AFTER graph expansion —
    it sees the augmented set, not the raw vector hits."""

    class _CapturingReranker(Reranker):
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
            limit = top_k if top_k is not None else len(candidates)
            return list(candidates)[:limit]

        async def close(self) -> None:
            pass

    vec_store, graph_store = await _seeded_stores(
        docs={"a": "alpha", "b": "beta", "c": "gamma"},
        edges=[("a", "b", "CITES"), ("b", "c", "CITES")],
    )
    embedder = _FakeEmbedder(dim=4)
    ranker = _CapturingReranker()
    retriever = Retriever(
        store=vec_store,
        embedder=embedder,
        top_k=2,
        over_fetch_factor=1,
        reranker=ranker,
        graph_expansion=GraphExpansion(store=graph_store, max_hops=2, decay=0.5),
    )
    await retriever.retrieve("alpha")
    # The reranker should have seen the expanded set including b + c
    # from the graph traversal, not just the vector hit a.
    assert "a" in ranker.seen_ids
    assert "b" in ranker.seen_ids
    assert "c" in ranker.seen_ids


# ---------- Compose with hybrid mode ----------


@pytest.mark.asyncio
async def test_hybrid_mode_with_graph_expansion() -> None:
    """mode='hybrid' + graph_expansion: hybrid fuses vector + lexical,
    then graph expands the fused set."""
    vec_store, graph_store = await _seeded_stores(
        docs={"a": "alpha doc", "b": "beta doc", "c": "gamma doc"},
        edges=[("a", "b", "CITES"), ("b", "c", "CITES")],
    )
    embedder = _FakeEmbedder(dim=4)
    retriever = Retriever(
        store=vec_store,
        embedder=embedder,
        top_k=1,
        over_fetch_factor=1,
        mode="hybrid",
        graph_expansion=GraphExpansion(store=graph_store, max_hops=2, decay=0.5),
    )
    results = await retriever.retrieve("alpha")
    ids = {m.id for m in results}
    # The hybrid base should surface `a` (matches "alpha" lexically);
    # graph expansion adds b, c.
    assert {"a", "b", "c"}.issubset(ids)
