"""`VectorStore` — locked semantic-search ABC.

A vector store is distinct from `MemoryStore` (the claim audit log):
the shapes don't unify cleanly. Vectors search by similarity; claims
filter by structured metadata + monotonic ULID ordering. We keep two
separate ABCs and a user who wants similarity over claims puts the
claim text into a vector store with `metadata={"claim_id": <id>}`.

Per ADR-0007 the surface is locked at v0.1: adding a method is a
major version bump. Optional capabilities (e.g. native ANN indexes,
hybrid search) layer the same way as `LLMClient` capabilities —
declared via `capabilities()` and gated via `supports()`.

Conformance: every shipped or third-party driver must pass
`agentforge_core.testing.run_vector_conformance` (lands alongside
this contract).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agentforge_core.values.vector import VectorItem, VectorMatch


class VectorStore(ABC):
    """Provider-agnostic vector index.

    Implementations:
      - declare a fixed `dimensions()` — every upserted vector and
        every search vector must match
      - normalise scores to cosine similarity in `[0, 1]` regardless
        of internal distance metric (drivers convert at the boundary)
      - implement metadata filtering as conjunctive equality on every
        key/value pair the caller passes

    Cross-driver invariants enforced by the conformance suite:
      - upsert(id=X) followed by upsert(id=X) replaces the prior
        record (write-through semantics)
      - search returns at most `limit` items, sorted by score desc
      - dimension mismatch on upsert or search raises `ValueError`
    """

    @abstractmethod
    async def upsert(self, items: list[VectorItem]) -> None:
        """Insert or replace `items`.

        If two items in `items` share an id, the last one wins. Callers
        wanting transactional all-or-nothing semantics should batch via
        a single `upsert` call (drivers may still split the request
        internally).

        Raises:
            ValueError: a vector's length does not match `dimensions()`.
        """

    @abstractmethod
    async def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Return the top-`limit` items by cosine similarity.

        Args:
            query_vector: Length must equal `dimensions()`.
            limit: Maximum results to return. Drivers may return fewer.
            filter_metadata: Conjunctive equality filter on the items'
                `metadata` dict. `None` means no filtering.

        Raises:
            ValueError: dimension mismatch or `limit < 1`.
        """

    @abstractmethod
    async def delete(self, ids: list[str]) -> int:
        """Delete by id. Returns the number of items actually removed.

        Unknown ids are silently ignored (no exception). Empty `ids`
        list returns 0.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release backing resources (connections, file handles)."""

    @abstractmethod
    def dimensions(self) -> int:
        """The fixed vector dimensionality this store accepts.

        Synchronous so callers can size storage / validate input
        without a network round-trip.
        """

    def capabilities(self) -> set[str]:
        """Optional capabilities this driver supports.

        Default empty set. Closed vocabulary (additions are minor
        bumps): `"native_ann"` (driver uses an ANN index rather than
        brute force), `"hybrid_search"` (BM25 + vector fusion),
        `"transactions"` (multi-statement atomic upserts).
        """
        return set()

    def supports(self, capability: str) -> bool:
        """True if this driver declares the given capability."""
        return capability in self.capabilities()
