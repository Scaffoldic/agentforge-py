"""Unit tests for the `MemoryStore` ABC."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import pytest
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.values.claim import Claim


def test_memorystore_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError, match="abstract"):
        MemoryStore()  # type: ignore[abstract]


class _MinimalStore(MemoryStore):
    """Minimal subclass overriding every abstract method."""

    def __init__(self) -> None:
        self._items: dict[str, Claim] = {}

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
        return list(self._items.values())[:limit]

    async def supersede(self, old_id: str, new_claim: Claim) -> str:
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
            for c in self._items.values():
                yield c

        return _agen()

    async def delete(
        self,
        *,
        run_id: str | None = None,
        older_than: datetime | None = None,
        category: str | None = None,
    ) -> int:
        del older_than
        keep: dict[str, Claim] = {}
        removed = 0
        for cid, c in self._items.items():
            if run_id is not None and c.run_id != run_id:
                keep[cid] = c
                continue
            if category is not None and c.category != category:
                keep[cid] = c
                continue
            removed += 1
        self._items = keep
        return removed

    async def close(self) -> None:
        self._items.clear()


def _claim() -> Claim:
    return Claim(
        run_id="r1",
        project="p",
        agent="a",
        category="finding",
        payload={"x": 1},
    )


@pytest.mark.asyncio
async def test_minimal_subclass_put_and_get() -> None:
    store = _MinimalStore()
    c = _claim()
    cid = await store.put(c)
    assert cid == c.id
    fetched = await store.get(cid)
    assert fetched is c


@pytest.mark.asyncio
async def test_minimal_subclass_query() -> None:
    store = _MinimalStore()
    await store.put(_claim())
    await store.put(_claim())
    results = await store.query()
    assert len(results) == 2


@pytest.mark.asyncio
async def test_minimal_subclass_stream() -> None:
    store = _MinimalStore()
    await store.put(_claim())
    collected = [c async for c in store.stream()]
    assert len(collected) == 1


@pytest.mark.asyncio
async def test_minimal_subclass_close() -> None:
    store = _MinimalStore()
    await store.put(_claim())
    await store.close()
    assert await store.get("anything") is None


def test_default_capabilities_is_empty() -> None:
    assert _MinimalStore().capabilities() == set()


def test_supports_uses_capabilities() -> None:
    class _GraphStore(_MinimalStore):
        def capabilities(self) -> set[str]:
            return {"graph"}

    g = _GraphStore()
    assert g.supports("graph") is True
    assert g.supports("vector") is False
