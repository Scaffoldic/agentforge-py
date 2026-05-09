"""`MemoryStore` — the locked persistence ABC.

feat-001 ships the contract plus an `InMemoryStore` reference impl in
the runtime package. feat-005 adds drivers for SQLite, PostgreSQL,
SurrealDB, and Neo4j (all passing the same conformance suite per
ADR-0007 and feat-016's `run_memory_conformance`).

Per feat-005's design (`docs/design/persistence-and-orm.md`), every
driver implements `MemoryStore`; graph-capable drivers additionally
implement `GraphStore` (deferred to feat-005).

Cross-agent isolation: every query is scoped by `(project, agent)` by
default. Cross-scope access requires explicit `None` filters — a
deliberate verb, not an accident.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from agentforge_core.values.claim import Claim


class MemoryStore(ABC):
    """Persistent store of `Claim`s with `(project, agent)` namespacing."""

    @abstractmethod
    async def put(self, claim: Claim) -> str:
        """Persist `claim`. Returns its id (the claim's own ULID by default)."""

    @abstractmethod
    async def get(self, claim_id: str) -> Claim | None:
        """Fetch a claim by id, or None if not present."""

    @abstractmethod
    async def query(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[Claim]:
        """Query claims with the given filters.

        Filters are conjunctive. Passing `None` for `project` or `agent`
        explicitly broadens the scope (cross-scope access is a verb).
        """

    @abstractmethod
    async def supersede(self, old_id: str, new_claim: Claim) -> str:
        """Replace `old_id` with `new_claim`; preserves history.

        Sets `new_claim.supersedes = old_id` if not already set; returns
        the new claim's id.
        """

    @abstractmethod
    def stream(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
    ) -> AsyncIterator[Claim]:
        """Stream all matching claims as an async iterator.

        Required even on backends with paged queries — drivers paginate
        internally and yield `Claim`s as they arrive.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release backing resources (connections, file handles)."""

    def capabilities(self) -> set[str]:
        """Optional capabilities this driver supports.

        Default empty set. Subclasses declare capabilities from the
        closed vocabulary: "graph", "vector", "fts", "transactions",
        "ttl", "encryption_at_rest". Per ADR-0009, declarations must be
        honest — a nightly conformance test exercises every declared
        capability against the real backend.
        """
        return set()

    def supports(self, capability: str) -> bool:
        """True if this driver declares the given capability."""
        return capability in self.capabilities()
