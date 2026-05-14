"""`Retriever` — high-level adapter over `VectorStore` + `EmbeddingClient`.

A vector store on its own takes vectors; a retriever takes *text*
and routes it through an embedder so callers can think in documents
and queries instead of raw floats.

Typical use:

    retriever = Retriever(store=store, embedder=embedder, top_k=5)
    await retriever.add_documents([
        "Paris is the capital of France.",
        "The Louvre is in Paris.",
    ])
    matches = await retriever.retrieve("Where is the Louvre?")

The retriever owns no state of its own — calling `close()` is a
courtesy that closes the underlying store and embedder for the
caller. Multi-retriever-over-one-store setups should not call
`close()` on the retriever.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Literal

from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.vector import VectorItem, VectorMatch
from ulid import ULID

RetrieverMode = Literal["vector", "hybrid"]
"""Retrieval mode: ``"vector"`` (default; cosine search only) or
``"hybrid"`` (BM25 + cosine fused via Reciprocal Rank Fusion).

Hybrid mode requires the underlying ``VectorStore`` to declare the
``"hybrid_search"`` capability (feat-022)."""


class Retriever:
    """Wraps `VectorStore` + `EmbeddingClient` for text-in / text-out RAG.

    Args:
        store: Backing `VectorStore`. Its `dimensions()` must match
            `embedder.dimensions()`.
        embedder: Backing `EmbeddingClient`.
        top_k: Default match count returned by `retrieve()`. Callers
            can override per-call via the `top_k` kwarg.
        batch_size: Maximum texts per embedding call when adding
            documents. Bedrock Titan loops one-at-a-time anyway, but
            other providers (Cohere, OpenAI) batch natively; tuning
            this is a per-provider concern.
        reranker: Optional `Reranker` to apply after the initial
            vector search. When set, `retrieve()` pulls
            ``top_k * over_fetch_factor`` candidates from the store
            and reranks them down to ``top_k``. None disables
            reranking (feat-021 default).
        over_fetch_factor: Multiplier for the candidate pool size
            when a reranker is configured. Default 3 (Cohere /
            Voyage best practice). Set to 1 to disable over-fetch
            even when a reranker is set; ignored when
            ``reranker is None``.

    Raises:
        ValueError: store and embedder dimensions don't match,
            ``top_k`` / ``batch_size`` / ``over_fetch_factor`` are
            not positive.
    """

    def __init__(
        self,
        *,
        store: VectorStore,
        embedder: EmbeddingClient,
        top_k: int = 5,
        batch_size: int = 32,
        reranker: Reranker | None = None,
        over_fetch_factor: int = 3,
        mode: RetrieverMode = "vector",
        rrf_k: int = 60,
    ) -> None:
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")
        if over_fetch_factor < 1:
            raise ValueError(f"over_fetch_factor must be >= 1, got {over_fetch_factor}")
        if rrf_k < 1:
            raise ValueError(f"rrf_k must be >= 1, got {rrf_k}")
        if mode not in ("vector", "hybrid"):
            raise ValueError(f"mode must be 'vector' or 'hybrid', got {mode!r}")
        if mode == "hybrid" and not store.supports("hybrid_search"):
            raise ValueError(
                f"Retriever(mode='hybrid') requires a VectorStore that "
                f"declares the 'hybrid_search' capability; "
                f"{type(store).__name__} does not."
            )
        if store.dimensions() != embedder.dimensions():
            raise ValueError(
                f"store dimensions ({store.dimensions()}) do not match "
                f"embedder dimensions ({embedder.dimensions()})"
            )
        self._store = store
        self._embedder = embedder
        self._top_k = top_k
        self._batch_size = batch_size
        self._reranker = reranker
        self._over_fetch_factor = over_fetch_factor
        self._mode: RetrieverMode = mode
        self._rrf_k = rrf_k

    @property
    def store(self) -> VectorStore:
        return self._store

    @property
    def embedder(self) -> EmbeddingClient:
        return self._embedder

    @property
    def reranker(self) -> Reranker | None:
        return self._reranker

    @property
    def mode(self) -> RetrieverMode:
        return self._mode

    @property
    def rrf_k(self) -> int:
        return self._rrf_k

    async def add_documents(
        self,
        texts: list[str],
        *,
        ids: list[str] | None = None,
        metadata: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Embed and upsert `texts` into the store.

        Args:
            texts: One or more documents to index. Empty list is a no-op.
            ids: Optional caller-supplied ids. If omitted, ULIDs are
                generated. Length must match `texts`.
            metadata: Optional per-document metadata. Length must match
                `texts`. Defaults to empty dict per document.

        Returns:
            The list of ids actually stored (caller-supplied or
            generated), in the order of the input texts.

        Raises:
            ValueError: `ids` or `metadata` length disagrees with `texts`.
        """
        if not texts:
            return []
        if ids is not None and len(ids) != len(texts):
            raise ValueError(f"ids has {len(ids)} entries but texts has {len(texts)}")
        if metadata is not None and len(metadata) != len(texts):
            raise ValueError(f"metadata has {len(metadata)} entries but texts has {len(texts)}")

        resolved_ids = ids if ids is not None else [str(ULID()) for _ in texts]
        resolved_meta = metadata if metadata is not None else [{} for _ in texts]

        # Embed in batches; Cohere supports native batching, Titan
        # loops internally — driver decides the actual fan-out.
        items: list[VectorItem] = []
        for start in range(0, len(texts), self._batch_size):
            chunk = texts[start : start + self._batch_size]
            response = await self._embedder.embed(chunk)
            for offset, vector in enumerate(response.vectors):
                global_idx = start + offset
                items.append(
                    VectorItem(
                        id=resolved_ids[global_idx],
                        vector=tuple(vector),
                        text=chunk[offset],
                        metadata=resolved_meta[global_idx],
                    )
                )

        await self._store.upsert(items)
        return resolved_ids

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Embed `query` and return the top matches from the store.

        When a `Reranker` is configured, the retriever first pulls
        ``top_k * over_fetch_factor`` candidates from the vector
        store, then reranks them down to ``top_k``. Without a
        reranker the original ``top_k`` candidates are returned
        as-is.

        Args:
            query: The user's question / prompt to embed and search.
            top_k: Override the constructor's default. Must be >= 1.
            filter_metadata: Conjunctive equality filter on items'
                metadata (forwarded to `VectorStore.search`).

        Raises:
            ValueError: `top_k` < 1.
        """
        limit = top_k if top_k is not None else self._top_k
        if limit < 1:
            raise ValueError(f"top_k must be >= 1, got {limit}")

        if self._mode == "hybrid":
            return await self._retrieve_hybrid(query, limit=limit, filter_metadata=filter_metadata)

        response = await self._embedder.embed([query])
        query_vector = tuple(response.vectors[0])
        over_fetch = limit * self._over_fetch_factor if self._reranker is not None else limit
        candidates = await self._store.search(
            query_vector,
            limit=over_fetch,
            filter_metadata=filter_metadata,
        )
        if self._reranker is None:
            return candidates
        return await self._reranker.rerank(query, candidates, top_k=limit)

    async def _retrieve_hybrid(
        self,
        query: str,
        *,
        limit: int,
        filter_metadata: dict[str, Any] | None,
    ) -> list[VectorMatch]:
        """Hybrid retrieval: vector + lexical fused via RRF.

        Pulls ``limit * over_fetch_factor`` from each path in
        parallel, fuses by rank, optionally reranks the fused
        candidate set, returns top-``limit``.
        """
        candidate_width = limit * self._over_fetch_factor
        response = await self._embedder.embed([query])
        query_vector = tuple(response.vectors[0])
        vec_task = self._store.search(
            query_vector, limit=candidate_width, filter_metadata=filter_metadata
        )
        lex_task = self._store.lexical_search(
            query, limit=candidate_width, filter_metadata=filter_metadata
        )
        vec_matches, lex_matches = await asyncio.gather(vec_task, lex_task)
        fused = self._rrf_fuse(vec_matches, lex_matches, limit=candidate_width)
        if self._reranker is None:
            return fused[:limit]
        return await self._reranker.rerank(query, fused, top_k=limit)

    def _rrf_fuse(
        self,
        vec: list[VectorMatch],
        lex: list[VectorMatch],
        *,
        limit: int,
    ) -> list[VectorMatch]:
        """Fuse two ranked lists via Reciprocal Rank Fusion.

        ``RRF_score(d) = Σ_L 1 / (k + rank_L(d))`` where ``rank_L(d)``
        is the 1-indexed rank of ``d`` in list ``L`` (omitted from
        the sum when ``d`` is absent). Cormack/Clarke/Büttcher 2009.
        The fused score is written onto the returned ``VectorMatch``
        objects; callers that need the per-path scores must inspect
        the inputs themselves.
        """
        scores: dict[str, float] = defaultdict(float)
        matches_by_id: dict[str, VectorMatch] = {}
        for rank, m in enumerate(vec, start=1):
            scores[m.id] += 1.0 / (self._rrf_k + rank)
            matches_by_id[m.id] = m
        for rank, m in enumerate(lex, start=1):
            scores[m.id] += 1.0 / (self._rrf_k + rank)
            matches_by_id.setdefault(m.id, m)
        fused_ids = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [matches_by_id[id_].model_copy(update={"score": score}) for id_, score in fused_ids]

    async def close(self) -> None:
        """Close the underlying store, embedder, and reranker.

        Convenience for callers that own all three. If the retriever
        shares any of them with other components, do NOT call this.
        """
        await self._store.close()
        await self._embedder.close()
        if self._reranker is not None:
            await self._reranker.close()


__all__ = ["Retriever"]
