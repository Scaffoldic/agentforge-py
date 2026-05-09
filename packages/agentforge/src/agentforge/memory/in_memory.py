"""`InMemoryStore` — process-local `MemoryStore` implementation.

Used as the default when no persistence module is configured. Loses
data on process exit (by design — for tests, demos, ephemeral runs).
For durable storage swap to a feat-005 driver via `agentforge.yaml`.

Implementation notes:

  - Storage is an `OrderedDict[str, Claim]` keyed by claim id, so
    insertion order is preserved (sortable ULID ids already provide
    monotonic ordering, but the dict guarantees it after deletes /
    supersedes).
  - All operations are ``async def`` to match the `MemoryStore`
    contract; they don't actually do I/O so they complete on the
    current event-loop tick.
  - Thread safety is NOT a goal — this is for in-process single-loop
    use. Multi-process / multi-worker deployments use feat-005 drivers.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import AsyncIterator

from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.claim import Claim


class InMemoryStore(MemoryStore):
    """Process-local `MemoryStore` backed by an in-memory ``OrderedDict``."""

    def __init__(self) -> None:
        self._items: OrderedDict[str, Claim] = OrderedDict()

    async def put(self, claim: Claim) -> str:
        self._items[claim.id] = claim
        return claim.id

    async def get(self, claim_id: str) -> Claim | None:
        return self._items.get(claim_id)

    async def query(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[Claim]:
        results: list[Claim] = []
        for claim in self._items.values():
            if project is not None and claim.project != project:
                continue
            if agent is not None and claim.agent != agent:
                continue
            if category is not None and claim.category != category:
                continue
            if run_id is not None and claim.run_id != run_id:
                continue
            results.append(claim)
            if len(results) >= limit:
                break
        return results

    async def supersede(self, old_id: str, new_claim: Claim) -> str:
        if old_id not in self._items:
            raise ModuleError(f"Cannot supersede unknown claim id: {old_id!r}")
        if new_claim.supersedes is None:
            new_claim = new_claim.model_copy(update={"supersedes": old_id})
        elif new_claim.supersedes != old_id:
            raise ModuleError(
                f"new_claim.supersedes={new_claim.supersedes!r} does not match old_id={old_id!r}"
            )
        self._items[new_claim.id] = new_claim
        return new_claim.id

    def stream(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
    ) -> AsyncIterator[Claim]:
        async def _agen() -> AsyncIterator[Claim]:
            for claim in list(self._items.values()):
                if project is not None and claim.project != project:
                    continue
                if agent is not None and claim.agent != agent:
                    continue
                if category is not None and claim.category != category:
                    continue
                if run_id is not None and claim.run_id != run_id:
                    continue
                yield claim

        return _agen()

    async def close(self) -> None:
        self._items.clear()
