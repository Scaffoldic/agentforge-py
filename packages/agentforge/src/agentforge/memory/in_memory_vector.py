"""`InMemoryVectorStore` — process-local `VectorStore` reference impl.

Brute-force cosine similarity over a Python dict. Suitable for tests,
demos, and small RAG corpora (~hundreds of items). Production
deployments swap to `agentforge-memory-sqlite` (zero-deps persistent)
or `agentforge-memory-postgres` (scaled, native ANN) — both pass the
same `run_vector_conformance` suite.

Design notes:

  - Dimensions are fixed at construction. Mismatched vectors raise
    `ValueError` immediately, before they can corrupt the index.
  - Search is O(N) per call — fine for small corpora, sluggish past
    a few thousand items. The capability vocabulary lets future
    drivers declare `"native_ann"`; this one does not.
  - Vectors are L2-normalised before storage so similarity is a
    plain dot product at search time. Callers don't have to
    pre-normalise.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from typing import Any

from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.vector import VectorItem, VectorMatch


class InMemoryVectorStore(VectorStore):
    """In-process `VectorStore` backed by a dict + brute-force search."""

    def __init__(self, *, dimensions: int) -> None:
        if dimensions < 1:
            raise ValueError(f"dimensions must be >= 1, got {dimensions}")
        self._dim = dimensions
        # id -> (normalised vector, text, metadata)
        self._items: OrderedDict[str, tuple[tuple[float, ...], str, dict[str, Any]]] = OrderedDict()

    def dimensions(self) -> int:
        return self._dim

    async def upsert(self, items: list[VectorItem]) -> None:
        for item in items:
            if len(item.vector) != self._dim:
                raise ValueError(
                    f"vector for id={item.id!r} has length {len(item.vector)} "
                    f"but store dimensions={self._dim}"
                )
            self._items[item.id] = (
                _l2_normalise(item.vector),
                item.text,
                dict(item.metadata),
            )

    async def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        if len(query_vector) != self._dim:
            raise ValueError(
                f"query vector has length {len(query_vector)} but store dimensions={self._dim}"
            )

        query = _l2_normalise(query_vector)
        scored: list[tuple[float, str, str, dict[str, Any]]] = []
        for item_id, (vec, text, meta) in self._items.items():
            if filter_metadata is not None and not _matches_filter(meta, filter_metadata):
                continue
            # Cosine similarity in [-1, 1]. Clamped to [0, 1]: 1.0
            # means identical direction, 0.0 means orthogonal-or-
            # anti-correlated. For text embeddings this drops
            # essentially no information (anti-correlation is rare).
            similarity = sum(a * b for a, b in zip(query, vec, strict=True))
            clamped = max(0.0, min(1.0, similarity))
            scored.append((clamped, item_id, text, meta))

        scored.sort(key=lambda row: row[0], reverse=True)
        top = scored[:limit]
        return [
            VectorMatch(id=item_id, text=text, metadata=dict(meta), score=score)
            for score, item_id, text, meta in top
        ]

    async def delete(self, ids: list[str]) -> int:
        removed = 0
        for item_id in ids:
            if self._items.pop(item_id, None) is not None:
                removed += 1
        return removed

    async def close(self) -> None:
        self._items.clear()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _l2_normalise(vector: tuple[float, ...]) -> tuple[float, ...]:
    """Return `vector / ||vector||`; falls back to the input if zero."""
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return vector
    return tuple(x / norm for x in vector)


def _matches_filter(metadata: dict[str, Any], filter_md: dict[str, Any]) -> bool:
    """True if every (k, v) in `filter_md` matches `metadata`."""
    return all(metadata.get(k) == v for k, v in filter_md.items())
