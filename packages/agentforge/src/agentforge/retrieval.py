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
import logging
from collections import defaultdict
from typing import Any, Literal

from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.graph import GraphNode
from agentforge_core.values.retrieval import GraphExpansion
from agentforge_core.values.vector import VectorItem, VectorMatch
from ulid import ULID

log = logging.getLogger(__name__)

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
        graph_expansion: GraphExpansion | None = None,
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
        self._graph_expansion = graph_expansion

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

    @property
    def graph_expansion(self) -> GraphExpansion | None:
        return self._graph_expansion

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

        # Stage 1 — base retrieval (vector or hybrid). Over-fetch when
        # a reranker is set so the reranker has a wider candidate pool;
        # otherwise pull exactly `limit` seeds.
        candidate_width = limit * self._over_fetch_factor if self._reranker is not None else limit
        if self._mode == "hybrid":
            candidates = await self._retrieve_hybrid_candidates(
                query, candidate_width=candidate_width, filter_metadata=filter_metadata
            )
        else:
            candidates = await self._retrieve_vector_candidates(
                query, candidate_width=candidate_width, filter_metadata=filter_metadata
            )

        # Stage 2 — optional graph expansion. Augments the candidate
        # set with N-hop neighbours of the seed hits. When no reranker
        # is configured, the expanded set is returned as-is (top_k is
        # treated as a minimum direct-hit count, not a hard cap).
        if self._graph_expansion is not None:
            candidates = await self._expand_via_graph(
                candidates,
                expansion=self._graph_expansion,
            )

        # Stage 3 — optional rerank narrows to top_k. Without a
        # reranker the candidate set is returned in seed-then-expansion
        # order; when no graph_expansion is set the slice is exactly
        # top_k, when graph_expansion is set the expansion neighbours
        # are appended after the top_k seeds.
        if self._reranker is None:
            if self._graph_expansion is None:
                return candidates[:limit]
            return candidates
        return await self._reranker.rerank(query, candidates, top_k=limit)

    async def _retrieve_vector_candidates(
        self,
        query: str,
        *,
        candidate_width: int,
        filter_metadata: dict[str, Any] | None,
    ) -> list[VectorMatch]:
        """Pure vector top-`candidate_width` retrieval (no rerank)."""
        response = await self._embedder.embed([query])
        query_vector = tuple(response.vectors[0])
        return await self._store.search(
            query_vector,
            limit=candidate_width,
            filter_metadata=filter_metadata,
        )

    async def _retrieve_hybrid_candidates(
        self,
        query: str,
        *,
        candidate_width: int,
        filter_metadata: dict[str, Any] | None,
    ) -> list[VectorMatch]:
        """Hybrid retrieval: vector + lexical fused via RRF.

        Pulls ``candidate_width`` from each path in parallel and fuses
        by rank. Reranking is the caller's responsibility (deferred to
        the unified pipeline in :meth:`retrieve`).
        """
        response = await self._embedder.embed([query])
        query_vector = tuple(response.vectors[0])
        vec_task = self._store.search(
            query_vector, limit=candidate_width, filter_metadata=filter_metadata
        )
        lex_task = self._store.lexical_search(
            query, limit=candidate_width, filter_metadata=filter_metadata
        )
        vec_matches, lex_matches = await asyncio.gather(vec_task, lex_task)
        return self._rrf_fuse(vec_matches, lex_matches, limit=candidate_width)

    async def _expand_via_graph(
        self,
        seeds: list[VectorMatch],
        *,
        expansion: GraphExpansion,
    ) -> list[VectorMatch]:
        """Expand each seed by traversing the graph up to
        ``expansion.max_hops`` hops; merge results with the seeds.

        Direct seeds keep their score + order at the head; expansion
        nodes follow, sorted by decayed score desc. Dedup is by id —
        the seed wins.
        """
        if not seeds:
            return []

        async def _reach(seed: VectorMatch) -> tuple[VectorMatch, list[tuple[int, GraphNode]]]:
            try:
                if expansion.direction == "any":
                    reaches = await self._reach_via_traverse(seed, expansion, n_seeds=len(seeds))
                else:
                    reaches = await self._reach_via_get_edges(seed, expansion)
            except Exception:
                log.debug("graph expansion failed for seed %s", seed.id, exc_info=True)
                return seed, []
            return seed, reaches

        results = await asyncio.gather(*(_reach(s) for s in seeds))

        seed_ids = {s.id for s in seeds}
        # Keyed by node id; track best (highest) decayed score per id —
        # since score = decay**depth (decay <= 1), the lowest-depth reach
        # wins, so this also picks the shortest path to each node.
        expanded_by_id: dict[str, tuple[float, int, VectorMatch]] = {}
        for seed, reaches in results:
            if not reaches:
                log.debug("no graph expansion found for seed %s", seed.id)
                continue
            for depth, node in reaches:
                if node.id in seed_ids:
                    continue
                score = float(seed.score) * (float(expansion.decay) ** depth)
                prior = expanded_by_id.get(node.id)
                if prior is not None and prior[0] >= score:
                    continue
                text = str(node.properties.get(expansion.text_property, ""))
                merged_meta: dict[str, Any] = dict(node.properties)
                merged_meta["agentforge.expanded_from"] = seed.id
                merged_meta["agentforge.hop"] = depth
                expanded_by_id[node.id] = (
                    score,
                    depth,
                    VectorMatch(id=node.id, text=text, metadata=merged_meta, score=score),
                )

        expansion_matches = sorted(
            (m for _, _, m in expanded_by_id.values()),
            key=lambda m: m.score,
            reverse=True,
        )
        return list(seeds) + expansion_matches

    @staticmethod
    async def _reach_via_traverse(
        seed: VectorMatch,
        expansion: GraphExpansion,
        *,
        n_seeds: int,
    ) -> list[tuple[int, GraphNode]]:
        """Undirected expansion (``direction="any"``) via the store's
        native ``traverse`` — the original feat-023 path, unchanged."""
        paths = await expansion.store.traverse(
            start_id=seed.id,
            edge_types=expansion.edge_types,
            max_depth=expansion.max_hops,
            limit=max(n_seeds, 1) * expansion.max_hops * 4,
        )
        # path.nodes[0] is the seed; nodes[i] is at depth i. Emit every
        # (depth, node); the caller's best-score dedup keeps the shortest.
        return [
            (depth, node) for path in paths for depth, node in enumerate(path.nodes) if depth > 0
        ]

    @staticmethod
    async def _reach_via_get_edges(
        seed: VectorMatch,
        expansion: GraphExpansion,
    ) -> list[tuple[int, GraphNode]]:
        """Directional expansion (``direction in {"out", "in"}``) via a
        BFS over the locked ``get_edges(direction=...)`` primitive — no
        ABC change (enh-005). ``out`` collects ``edge.dst``; ``in``
        collects ``edge.src``."""
        direction = expansion.direction
        edge_types = expansion.edge_types or (None,)
        visited: set[str] = {seed.id}
        frontier: set[str] = {seed.id}
        reaches: list[tuple[int, GraphNode]] = []
        for depth in range(1, expansion.max_hops + 1):
            neighbour_ids: set[str] = set()
            for node_id in frontier:
                for edge_type in edge_types:
                    edges = await expansion.store.get_edges(
                        node_id, edge_type=edge_type, direction=direction
                    )
                    for edge in edges:
                        nbr = edge.dst if direction == "out" else edge.src
                        if nbr not in visited:
                            neighbour_ids.add(nbr)
            if not neighbour_ids:
                break
            for nbr in neighbour_ids:
                visited.add(nbr)
                node = await expansion.store.get_node(nbr)
                if node is not None:
                    reaches.append((depth, node))
            frontier = neighbour_ids
        return reaches

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
