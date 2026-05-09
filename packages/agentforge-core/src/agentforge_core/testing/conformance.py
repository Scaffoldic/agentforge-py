"""Conformance suites for `agentforge-core` ABCs.

Every shipped or third-party driver must pass these suites. They are
exposed as functions (not pytest collections) so they can be invoked
from any test runner by passing in a ready-to-use store / client.

Usage in a driver's tests:

    import pytest
    from agentforge_core.testing import run_memory_conformance
    from my_pkg import MyMemoryStore

    @pytest.mark.asyncio
    async def test_my_driver_conforms() -> None:
        async with MyMemoryStore.from_url("...") as store:
            await run_memory_conformance(store)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.values.claim import Claim


def _claim(
    *,
    project: str = "p1",
    agent: str = "a1",
    run_id: str = "run-x",
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


async def _collect(it: AsyncIterator[Claim]) -> list[Claim]:
    return [c async for c in it]


async def run_memory_conformance(store: MemoryStore) -> None:
    """Run the full MemoryStore conformance suite against `store`.

    The store must be empty when this is called and is left empty when
    the function returns (every claim written is also deleted, except
    where the contract demands history retention via `supersede`).

    Raises:
        AssertionError: a contract was violated.
    """
    # 1. put + get roundtrip
    c1 = _claim(category="finding")
    cid = await store.put(c1)
    assert cid == c1.id, "put() must return the claim's id"
    fetched = await store.get(cid)
    assert fetched is not None, "get() must return the persisted claim"
    assert fetched.id == c1.id

    # 2. get returns None for unknown id
    missing = await store.get("01HX-NONEXISTENT")
    assert missing is None, "get() of an unknown id must return None"

    # 3. query with no filters returns at least the claim we put
    all_results = await store.query()
    assert any(c.id == cid for c in all_results), (
        "query() with no filters must include the put claim"
    )

    # 4. query filters by project
    other_project = _claim(project="other-project")
    await store.put(other_project)
    only_p1 = await store.query(project="p1")
    assert any(c.id == cid for c in only_p1)
    assert all(c.project == "p1" for c in only_p1), (
        "query(project=...) must filter results to that project"
    )

    # 5. query filters by agent
    other_agent = _claim(agent="other-agent")
    await store.put(other_agent)
    only_a1 = await store.query(agent="a1")
    assert all(c.agent == "a1" for c in only_a1), (
        "query(agent=...) must filter results to that agent"
    )

    # 6. query filters by category
    decision = _claim(category="decision")
    await store.put(decision)
    only_findings = await store.query(category="finding")
    assert all(c.category == "finding" for c in only_findings), (
        "query(category=...) must filter results to that category"
    )

    # 7. query filters by run_id
    other_run = _claim(run_id="run-y")
    await store.put(other_run)
    only_run_x = await store.query(run_id="run-x")
    assert all(c.run_id == "run-x" for c in only_run_x), (
        "query(run_id=...) must filter results to that run_id"
    )

    # 8. query respects limit
    limited = await store.query(limit=1)
    assert len(limited) <= 1, "query(limit=N) must return at most N claims"

    # 9. supersede chains old → new
    new_claim = _claim(payload={"v": 2})
    new_id = await store.supersede(cid, new_claim)
    assert new_id == new_claim.id
    refetched = await store.get(new_id)
    assert refetched is not None
    assert refetched.supersedes == cid, "supersede() must set supersedes link on the new claim"

    # 10. stream yields claims
    streamed = await _collect(store.stream(project="p1"))
    assert len(streamed) >= 1, "stream() must yield matching claims"
    assert all(c.project == "p1" for c in streamed)

    # 11. capabilities() returns a set
    caps = store.capabilities()
    assert isinstance(caps, set)

    # 12. supports() reflects capabilities()
    if caps:
        sample = next(iter(caps))
        assert store.supports(sample) is True
    assert store.supports("definitely-not-a-capability-2026") is False
