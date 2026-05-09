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

from typing import Any

from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.vector import VectorItem, VectorMatch
from ulid import ULID


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

    Raises:
        ValueError: store and embedder dimensions don't match, or
            `top_k`/`batch_size` are not positive.
    """

    def __init__(
        self,
        *,
        store: VectorStore,
        embedder: EmbeddingClient,
        top_k: int = 5,
        batch_size: int = 32,
    ) -> None:
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")
        if store.dimensions() != embedder.dimensions():
            raise ValueError(
                f"store dimensions ({store.dimensions()}) do not match "
                f"embedder dimensions ({embedder.dimensions()})"
            )
        self._store = store
        self._embedder = embedder
        self._top_k = top_k
        self._batch_size = batch_size

    @property
    def store(self) -> VectorStore:
        return self._store

    @property
    def embedder(self) -> EmbeddingClient:
        return self._embedder

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
        response = await self._embedder.embed([query])
        query_vector = tuple(response.vectors[0])
        return await self._store.search(
            query_vector,
            limit=limit,
            filter_metadata=filter_metadata,
        )

    async def close(self) -> None:
        """Close the underlying store and embedder.

        Convenience for callers that own both. If the retriever shares
        a store/embedder with other components, do NOT call this.
        """
        await self._store.close()
        await self._embedder.close()


__all__ = ["Retriever"]
