"""End-to-end YAML → Retriever smoke test (feat-021 follow-up chunk 3).

Drives the full path:

    agentforge.yaml (`retrieval:` block)
        ↓ load_config()
    AgentForgeConfig
        ↓ build_retriever_from_config()
    Retriever (wired with VectorStore + EmbeddingClient + Reranker)
        ↓ retrieve(query)
    list[VectorMatch] (reranked)

The three sub-components register under the
`vector_stores` / `embeddings` / `rerankers` resolver
categories via in-process `Resolver.register()` calls so the
test doesn't need an installed sister package.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from agentforge import InMemoryGraphStore, InMemoryVectorStore
from agentforge.cli._build import build_agent_from_config, build_retriever_from_config
from agentforge_core.config import load_config
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.resolver import Resolver
from agentforge_core.values.graph import GraphEdge, GraphNode
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage
from agentforge_core.values.vector import VectorMatch


class _FakeEmbedder(EmbeddingClient):
    def __init__(self, *, dim: int = 4) -> None:
        self._dim = dim

    @classmethod
    def from_config(cls, *, dim: int = 4) -> _FakeEmbedder:
        return cls(dim=dim)

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
        return None

    def dimensions(self) -> int:
        return self._dim


def _text_to_vector(text: str, dim: int) -> tuple[float, ...]:
    raw = [0.01] * dim
    for i, ch in enumerate(text):
        raw[i % dim] += ord(ch)
    norm = math.sqrt(sum(x * x for x in raw))
    return tuple(x / norm for x in raw) if norm > 0 else tuple(raw)


class _IntegrationVectorStore(InMemoryVectorStore):
    @classmethod
    def from_config(cls, *, dimensions: int = 4) -> _IntegrationVectorStore:
        return cls(dimensions=dimensions)


class _IntegrationGraphStore(InMemoryGraphStore):
    """Wraps the in-memory graph store so the resolver can build one.

    Pre-loaded with a tiny CITES chain so the YAML integration test
    can assert that graph expansion enriches the result set without
    having to populate the store in the test body.
    """

    _seeded: bool = False

    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def from_config(cls) -> _IntegrationGraphStore:
        return cls()


class _ReverseReranker(Reranker):
    """Reranker that reverses input order — easy to assert against."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @classmethod
    def from_config(cls) -> _ReverseReranker:
        return cls()

    async def rerank(
        self,
        query: str,
        candidates: list[VectorMatch],
        *,
        top_k: int | None = None,
    ) -> list[VectorMatch]:
        if top_k is not None and top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        self.calls.append((query, len(candidates)))
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
        return None


_INTEGRATION_YAML = """
agent:
  strategy: react
retrieval:
  vector_store:
    driver: integration-store
    config:
      dimensions: 4
  embedder:
    driver: integration-embedder
    config:
      dim: 4
  reranker:
    name: integration-reranker
    config: {}
  top_k: 2
  over_fetch_factor: 3
"""


@pytest.fixture
def registered() -> None:
    r = Resolver.global_()
    r.register("vector_stores", "integration-store", _IntegrationVectorStore)
    r.register("embeddings", "integration-embedder", _FakeEmbedder)
    r.register("rerankers", "integration-reranker", _ReverseReranker)
    r.register("graph_stores", "integration-graph", _IntegrationGraphStore)


@pytest.mark.asyncio
async def test_yaml_to_retriever_end_to_end(registered: None, tmp_path: Path) -> None:
    del registered
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text(_INTEGRATION_YAML)

    cfg = load_config(yaml_path)
    assert cfg.retrieval is not None
    assert cfg.retrieval.reranker is not None
    assert cfg.retrieval.reranker.name == "integration-reranker"
    assert cfg.retrieval.over_fetch_factor == 3

    retriever = build_retriever_from_config(cfg)
    assert retriever is not None
    assert isinstance(retriever.reranker, _ReverseReranker)

    # Index some documents and retrieve through the full pipeline.
    await retriever.add_documents(
        ["alpha doc", "beta doc", "gamma doc", "delta doc", "epsilon doc", "zeta doc"],
    )
    results = await retriever.retrieve("alpha query", top_k=2)

    # Reranker invoked exactly once with the over-fetch pool size.
    assert len(retriever.reranker.calls) == 1
    query, n_candidates = retriever.reranker.calls[0]
    assert query == "alpha query"
    assert n_candidates == 6  # top_k=2 * over_fetch_factor=3
    assert len(results) == 2


_HYBRID_YAML = """
agent:
  strategy: react
retrieval:
  mode: hybrid
  vector_store:
    driver: integration-store
    config:
      dimensions: 4
  embedder:
    driver: integration-embedder
    config:
      dim: 4
  top_k: 2
  over_fetch_factor: 1
  rrf_k: 60
"""


@pytest.mark.asyncio
async def test_yaml_hybrid_mode_to_retriever_end_to_end(registered: None, tmp_path: Path) -> None:
    """feat-022: `retrieval.mode: hybrid` round-trips through the
    config loader and produces a hybrid-mode Retriever that fuses
    vector + lexical paths."""
    del registered
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text(_HYBRID_YAML)

    cfg = load_config(yaml_path)
    assert cfg.retrieval is not None
    assert cfg.retrieval.mode == "hybrid"
    assert cfg.retrieval.rrf_k == 60

    retriever = build_retriever_from_config(cfg)
    assert retriever is not None
    assert retriever.mode == "hybrid"
    assert retriever.rrf_k == 60

    await retriever.add_documents(
        ["Paris is the capital of France", "The Eiffel Tower is iconic in Paris"],
    )
    results = await retriever.retrieve("Eiffel", top_k=2)
    # Both docs surface — hybrid fuses vector + lexical paths.
    assert len(results) == 2


_GRAPHRAG_YAML = """
agent:
  strategy: react
retrieval:
  vector_store:
    driver: integration-store
    config:
      dimensions: 4
  embedder:
    driver: integration-embedder
    config:
      dim: 4
  top_k: 1
  over_fetch_factor: 1
  graph_expansion:
    store:
      driver: integration-graph
      config: {}
    max_hops: 2
    edge_types: [CITES]
    text_property: text
    decay: 0.5
"""


@pytest.mark.asyncio
async def test_yaml_graph_expansion_to_retriever_end_to_end(
    registered: None, tmp_path: Path
) -> None:
    """feat-023: `retrieval.graph_expansion` round-trips through the
    config loader and produces a Retriever that augments vector hits
    with N-hop graph neighbours."""
    del registered
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text(_GRAPHRAG_YAML)

    cfg = load_config(yaml_path)
    assert cfg.retrieval is not None
    assert cfg.retrieval.graph_expansion is not None
    assert cfg.retrieval.graph_expansion.max_hops == 2
    assert cfg.retrieval.graph_expansion.edge_types == ["CITES"]

    retriever = build_retriever_from_config(cfg)
    assert retriever is not None
    assert retriever.graph_expansion is not None

    # Seed the graph store (resolved by the builder; reachable via the
    # retriever's GraphExpansion) with a CITES chain matching the
    # vector ids we'll add below.
    graph_store = retriever.graph_expansion.store
    await graph_store.add_node(GraphNode(id="a", labels=("Doc",), properties={"text": "alpha"}))
    await graph_store.add_node(GraphNode(id="b", labels=("Doc",), properties={"text": "beta"}))
    await graph_store.add_node(GraphNode(id="c", labels=("Doc",), properties={"text": "gamma"}))
    await graph_store.add_edge(GraphEdge(src="a", dst="b", edge_type="CITES"))
    await graph_store.add_edge(GraphEdge(src="b", dst="c", edge_type="CITES"))

    await retriever.add_documents(["alpha", "beta", "gamma"], ids=["a", "b", "c"])
    results = await retriever.retrieve("alpha")
    ids = {m.id for m in results}
    # vector seed = `a`; graph expansion appends `b` (1 hop) and `c`
    # (2 hops) via the CITES chain.
    assert {"a", "b", "c"}.issubset(ids)


@pytest.mark.asyncio
async def test_build_agent_from_config_threads_retriever(registered: None, tmp_path: Path) -> None:
    """feat-021 follow-up: `build_agent_from_config` now threads the
    Retriever returned by `build_retriever_from_config` into the
    Agent constructor (Agent already accepts `retriever=` and stores
    it on `RuntimeContext.retriever`)."""
    del registered
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text(_INTEGRATION_YAML)

    cfg = load_config(yaml_path)
    agent = await build_agent_from_config(cfg)
    try:
        # Agent constructed with the YAML's retrieval: block has the
        # retriever threaded in via build_agent_from_config.
        assert agent._retriever is not None
        assert isinstance(agent._retriever.reranker, _ReverseReranker)
    finally:
        await agent.close()
