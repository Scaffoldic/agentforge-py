"""Unit tests for `build_retriever_from_config` (feat-021 follow-up)."""

from __future__ import annotations

import math

import pytest
from agentforge import InMemoryVectorStore
from agentforge.cli._build import build_retriever_from_config
from agentforge_core.config import (
    AgentForgeConfig,
    ModuleEntry,
    RerankerEntry,
    RetrievalConfig,
)
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import Resolver
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage
from agentforge_core.values.vector import VectorMatch


class _FakeEmbedder(EmbeddingClient):
    """Embedder registered under `embeddings:fake-embedder` for tests."""

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


class _FakeInMemoryStore(InMemoryVectorStore):
    """Wraps InMemoryVectorStore so we can register it under
    `vector_stores:fake-store` via a from_config classmethod."""

    @classmethod
    def from_config(cls, *, dimensions: int = 4) -> _FakeInMemoryStore:
        return cls(dimensions=dimensions)


class _IdentityReranker(Reranker):
    """Reranker registered under `rerankers:identity-test` for tests."""

    def __init__(self, *, normaliser_floor: float = 0.0) -> None:
        self._floor = normaliser_floor
        self.invocations: list[str] = []

    @classmethod
    def from_config(cls, *, normaliser_floor: float = 0.0) -> _IdentityReranker:
        return cls(normaliser_floor=normaliser_floor)

    async def rerank(
        self,
        query: str,
        candidates: list[VectorMatch],
        *,
        top_k: int | None = None,
    ) -> list[VectorMatch]:
        del query
        if top_k is not None and top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        sorted_ = sorted(candidates, key=lambda m: m.score, reverse=True)
        if top_k is not None:
            return sorted_[:top_k]
        return sorted_

    async def close(self) -> None:
        return None


@pytest.fixture
def registered_resolver() -> Resolver:
    """Register the three test classes under the resolver categories
    they'll resolve from. Resolver is a process-global singleton, so we
    register-once-per-test-process via Resolver.global_()."""
    r = Resolver.global_()
    r.register("vector_stores", "fake-store", _FakeInMemoryStore)
    r.register("embeddings", "fake-embedder", _FakeEmbedder)
    r.register("rerankers", "identity-test", _IdentityReranker)
    return r


def test_returns_none_when_retrieval_block_absent(registered_resolver: Resolver) -> None:
    del registered_resolver
    cfg = AgentForgeConfig()
    assert build_retriever_from_config(cfg) is None


def test_builds_retriever_without_reranker(registered_resolver: Resolver) -> None:
    del registered_resolver
    cfg = AgentForgeConfig(
        retrieval=RetrievalConfig(
            vector_store=ModuleEntry(driver="fake-store", config={"dimensions": 4}),
            embedder=ModuleEntry(driver="fake-embedder", config={"dim": 4}),
            top_k=3,
        ),
    )
    retriever = build_retriever_from_config(cfg)
    assert retriever is not None
    assert retriever.reranker is None
    assert isinstance(retriever.store, _FakeInMemoryStore)
    assert isinstance(retriever.embedder, _FakeEmbedder)


def test_builds_retriever_with_reranker_and_overfetch(
    registered_resolver: Resolver,
) -> None:
    del registered_resolver
    cfg = AgentForgeConfig(
        retrieval=RetrievalConfig(
            vector_store=ModuleEntry(driver="fake-store", config={"dimensions": 4}),
            embedder=ModuleEntry(driver="fake-embedder", config={"dim": 4}),
            reranker=RerankerEntry(name="identity-test", config={"normaliser_floor": 0.1}),
            top_k=2,
            over_fetch_factor=4,
        ),
    )
    retriever = build_retriever_from_config(cfg)
    assert retriever is not None
    assert isinstance(retriever.reranker, _IdentityReranker)
    # over_fetch_factor + top_k threaded through the constructor.
    assert retriever._over_fetch_factor == 4
    assert retriever._top_k == 2


def test_unregistered_driver_raises(registered_resolver: Resolver) -> None:
    del registered_resolver
    cfg = AgentForgeConfig(
        retrieval=RetrievalConfig(
            vector_store=ModuleEntry(driver="this-does-not-exist", config={}),
            embedder=ModuleEntry(driver="fake-embedder", config={"dim": 4}),
        ),
    )
    with pytest.raises(ModuleError, match="vector_stores"):
        build_retriever_from_config(cfg)


def test_resolved_class_with_wrong_abc_raises(registered_resolver: Resolver) -> None:
    """If a registered class doesn't implement the expected ABC, the
    builder raises ModuleError with a clear message."""
    r = Resolver.global_()

    class _NotAVectorStore:
        @classmethod
        def from_config(cls) -> _NotAVectorStore:
            return cls()

    r.register("vector_stores", "bogus", _NotAVectorStore)
    cfg = AgentForgeConfig(
        retrieval=RetrievalConfig(
            vector_store=ModuleEntry(driver="bogus", config={}),
            embedder=ModuleEntry(driver="fake-embedder", config={"dim": 4}),
        ),
    )
    with pytest.raises(ModuleError, match="does not implement VectorStore"):
        build_retriever_from_config(cfg)
