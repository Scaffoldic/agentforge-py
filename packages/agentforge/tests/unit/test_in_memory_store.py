"""Unit tests for `InMemoryStore` — `MemoryStore` reference implementation."""

from __future__ import annotations

import pytest
from agentforge.memory import InMemoryStore
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.claim import Claim


def _claim(
    *,
    project: str = "p",
    agent: str = "a",
    run_id: str = "r",
    category: str = "finding",
    payload: dict[str, object] | None = None,
) -> Claim:
    return Claim(
        run_id=run_id,
        project=project,
        agent=agent,
        category=category,
        payload=payload if payload is not None else {"v": 1},
    )


@pytest.fixture
async def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.mark.asyncio
async def test_put_returns_id(store: InMemoryStore) -> None:
    c = _claim()
    cid = await store.put(c)
    assert cid == c.id


@pytest.mark.asyncio
async def test_get_returns_claim(store: InMemoryStore) -> None:
    c = _claim()
    await store.put(c)
    fetched = await store.get(c.id)
    assert fetched is c


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown_id(store: InMemoryStore) -> None:
    assert await store.get("01HX-NONEXISTENT") is None


@pytest.mark.asyncio
async def test_query_no_filters_returns_all(store: InMemoryStore) -> None:
    a = _claim()
    b = _claim()
    await store.put(a)
    await store.put(b)
    results = await store.query()
    assert len(results) == 2


@pytest.mark.asyncio
async def test_query_filters_by_project(store: InMemoryStore) -> None:
    await store.put(_claim(project="p1"))
    await store.put(_claim(project="p2"))
    results = await store.query(project="p1")
    assert len(results) == 1
    assert results[0].project == "p1"


@pytest.mark.asyncio
async def test_query_filters_by_agent(store: InMemoryStore) -> None:
    await store.put(_claim(agent="a1"))
    await store.put(_claim(agent="a2"))
    assert all(c.agent == "a1" for c in await store.query(agent="a1"))


@pytest.mark.asyncio
async def test_query_filters_by_category(store: InMemoryStore) -> None:
    await store.put(_claim(category="finding"))
    await store.put(_claim(category="decision"))
    assert all(c.category == "finding" for c in await store.query(category="finding"))


@pytest.mark.asyncio
async def test_query_filters_by_run_id(store: InMemoryStore) -> None:
    await store.put(_claim(run_id="r1"))
    await store.put(_claim(run_id="r2"))
    assert all(c.run_id == "r1" for c in await store.query(run_id="r1"))


@pytest.mark.asyncio
async def test_query_combines_filters(store: InMemoryStore) -> None:
    await store.put(_claim(project="p", agent="a"))
    await store.put(_claim(project="p", agent="other"))
    await store.put(_claim(project="other", agent="a"))
    results = await store.query(project="p", agent="a")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_query_respects_limit(store: InMemoryStore) -> None:
    for _ in range(5):
        await store.put(_claim())
    assert len(await store.query(limit=3)) == 3


@pytest.mark.asyncio
async def test_supersede_links_old_to_new(store: InMemoryStore) -> None:
    old = _claim()
    await store.put(old)
    new = _claim(payload={"v": 2})
    await store.supersede(old.id, new)
    refetched = await store.get(new.id)
    assert refetched is not None
    assert refetched.supersedes == old.id


@pytest.mark.asyncio
async def test_supersede_unknown_id_raises(store: InMemoryStore) -> None:
    new = _claim()
    with pytest.raises(ModuleError, match="Cannot supersede unknown"):
        await store.supersede("01HX-MISSING", new)


@pytest.mark.asyncio
async def test_supersede_with_mismatched_supersedes_raises(
    store: InMemoryStore,
) -> None:
    old = _claim()
    await store.put(old)
    new = Claim(
        run_id="r",
        project="p",
        agent="a",
        category="finding",
        payload={"v": 2},
        supersedes="01HX-OTHER",
    )
    with pytest.raises(ModuleError, match="does not match"):
        await store.supersede(old.id, new)


@pytest.mark.asyncio
async def test_stream_yields_filtered_claims(store: InMemoryStore) -> None:
    await store.put(_claim(project="p1"))
    await store.put(_claim(project="p2"))
    collected = [c async for c in store.stream(project="p1")]
    assert len(collected) == 1
    assert collected[0].project == "p1"


@pytest.mark.asyncio
async def test_close_clears_state(store: InMemoryStore) -> None:
    await store.put(_claim())
    await store.close()
    assert await store.query() == []


def test_default_capabilities_empty() -> None:
    assert InMemoryStore().capabilities() == set()
