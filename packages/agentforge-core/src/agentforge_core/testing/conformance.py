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

import itertools
import math
import typing
from collections.abc import AsyncIterator, Awaitable, Callable

from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.claim import Claim
from agentforge_core.values.state import AgentState, StepKind
from agentforge_core.values.vector import VectorItem

_VALID_STEP_KINDS: frozenset[str] = frozenset(typing.get_args(StepKind))
"""Closed enum mirror of `StepKind`. Used by `run_strategy_conformance`."""


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


# ----------------------------------------------------------------------
# Strategy conformance — feat-002.
# ----------------------------------------------------------------------


async def run_strategy_conformance(
    strategy: ReasoningStrategy,
    *,
    state_factory: Callable[[], AgentState],
    pre_run: Callable[[AgentState], None | Awaitable[None]] | None = None,
) -> None:
    """Run the shared `ReasoningStrategy` conformance suite.

    Args:
        strategy: A constructed strategy instance.
        state_factory: Builds a fresh `AgentState` for each scenario
            (with `RuntimeContext` bound on `state.metadata` if the
            strategy needs one — the framework runtime does this; tests
            must do it explicitly).
        pre_run: Optional async-or-sync callable invoked on the freshly
            built `AgentState` before `strategy.run()` (e.g. to seed
            findings or steps). May be omitted.

    Verifies the locked invariants of `ReasoningStrategy.run`:

      1. Returns the same `AgentState` instance it was given.
      2. Populates `state.steps` with at least one step.
      3. Every emitted step's `kind` is a valid `StepKind` value.
      4. `step.iteration` is monotonically non-decreasing across the run.
      5. Every emitted step has non-negative `tokens_in`, `tokens_out`,
         `cost_usd`, `duration_ms` (Pydantic enforces; the assertion
         here is defence-in-depth).

    Raises:
        AssertionError: a contract was violated.
    """
    state = state_factory()
    if pre_run is not None:
        outcome = pre_run(state)
        if outcome is not None and hasattr(outcome, "__await__"):
            await outcome

    result = await strategy.run(state)

    # 1. Returns the same instance
    assert result is state, (
        "ReasoningStrategy.run must return the same AgentState instance "
        "it received (state mutation, not replacement)."
    )

    # 2. Populates state.steps
    assert len(state.steps) >= 1, (
        "ReasoningStrategy.run must append at least one Step to state.steps before returning."
    )

    # 3. Every step.kind is valid
    for step in state.steps:
        assert step.kind in _VALID_STEP_KINDS, (
            f"step.kind={step.kind!r} is not a valid StepKind. "
            f"Valid kinds: {sorted(_VALID_STEP_KINDS)}"
        )

    # 4. step.iteration monotonic non-decreasing
    last_iter = -1
    for step in state.steps:
        assert step.iteration >= last_iter, (
            f"step.iteration must be monotonically non-decreasing; "
            f"saw {step.iteration} after {last_iter}."
        )
        last_iter = step.iteration

    # 5. Non-negative cost / token / duration fields (Pydantic
    #    already enforces ge=0; this is defence-in-depth)
    for step in state.steps:
        assert step.tokens_in >= 0, "step.tokens_in must be non-negative"
        assert step.tokens_out >= 0, "step.tokens_out must be non-negative"
        assert step.cost_usd >= 0.0, "step.cost_usd must be non-negative"
        assert step.duration_ms >= 0, "step.duration_ms must be non-negative"


# ----------------------------------------------------------------------
# Embedding conformance — feat-003.
# ----------------------------------------------------------------------


async def run_embedding_conformance(client: EmbeddingClient) -> None:
    """Run the shared `EmbeddingClient` conformance suite.

    Verifies the locked invariants of `EmbeddingClient.embed`:

      1. `dimensions()` returns a positive integer without a network
         round-trip (callers rely on this for storage sizing).
      2. `embed(texts)` raises `ValueError` on an empty input list
         (no provider supports zero-length batches).
      3. The returned `EmbeddingResponse` has one vector per input
         text in input order.
      4. Every vector has length `dimensions()`.
      5. `usage.input_tokens >= 0` and `usage.output_tokens == 0`
         (embeddings have no output tokens).
      6. `cost_usd >= 0`.
      7. `model` and `provider` are non-empty strings.
      8. `supports("not-a-real-capability")` returns False (the
         capability check is honest about unknown names).

    Drivers may need to issue a real (or mocked) network call inside
    this test, so it is async. Tests are responsible for arranging the
    necessary fixtures (e.g. injecting a fake AWS session) before
    calling this helper.

    Args:
        client: A constructed `EmbeddingClient` instance, ready to use.

    Raises:
        AssertionError: a contract was violated.
    """
    # 1. dimensions() is sync, positive, no network round-trip
    dim = client.dimensions()
    assert isinstance(dim, int), "dimensions() must return an int"
    assert dim >= 1, f"dimensions() must be >= 1, got {dim}"

    # 2. empty batch raises ValueError
    raised_value_error = False
    try:
        await client.embed([])
    except ValueError:
        raised_value_error = True
    assert raised_value_error, "embed([]) must raise ValueError on empty input"

    # 3-7. embed roundtrip
    texts = ["hello", "world", "agentforge"]
    response = await client.embed(texts)
    assert len(response.vectors) == len(texts), (
        f"embed() must return one vector per input text; "
        f"got {len(response.vectors)} vectors for {len(texts)} texts."
    )
    for i, vec in enumerate(response.vectors):
        assert len(vec) == dim, f"vector {i} has length {len(vec)} but dimensions() declared {dim}"
    assert response.dimensions == dim, (
        f"response.dimensions ({response.dimensions}) must match client.dimensions() ({dim})"
    )
    assert response.usage.input_tokens >= 0
    assert response.usage.output_tokens == 0, (
        f"embedding responses must report output_tokens=0; got {response.usage.output_tokens}."
    )
    assert response.cost_usd >= 0.0
    assert response.model, "EmbeddingResponse.model must be non-empty"
    assert response.provider, "EmbeddingResponse.provider must be non-empty"

    # 8. supports() is honest about unknown capabilities
    assert client.supports("definitely-not-a-capability-2026") is False


# ----------------------------------------------------------------------
# Vector store conformance — feat-007.
# ----------------------------------------------------------------------


async def run_vector_conformance(store: VectorStore) -> None:
    """Run the shared `VectorStore` conformance suite.

    The store must be empty when this is called and is left empty when
    the function returns (every item upserted is also deleted).

    Verifies the locked invariants of `VectorStore`:

      1. `dimensions()` returns a positive int with no network call.
      2. `upsert` accepts items whose vectors match `dimensions()`;
         dimension mismatch raises `ValueError`.
      3. `search` returns at most `limit` matches sorted by score
         descending, with scores in `[0, 1]`.
      4. `search`'s top hit on a query identical to an upserted
         vector returns that item with score ≈ 1.0.
      5. `upsert` is write-through: re-upserting an existing id
         replaces the prior record (no duplicate ids in results).
      6. `delete` returns the count of items actually removed; unknown
         ids are silently dropped (no exception).
      7. `filter_metadata` AND-matches every key/value in the dict.
      8. `search(limit=0)` raises `ValueError`.
      9. `supports("not-a-real-capability")` returns False.

    Drivers may issue real network calls; the suite is async. Tests are
    responsible for arranging fixtures (e.g. running Postgres) before
    calling this helper.

    Raises:
        AssertionError: a contract was violated.
    """
    _ITEM_COUNT = 3  # noqa: N806 — local constant in this function only

    dim = store.dimensions()
    assert isinstance(dim, int), "dimensions() must return an int"
    assert dim >= 1, f"dimensions() must be >= 1, got {dim}"

    # 2. dimension-mismatch on upsert
    bad = VectorItem(id="bad", vector=tuple([0.1] * (dim + 1)), text="bad", metadata={})
    raised_dim_error = False
    try:
        await store.upsert([bad])
    except ValueError:
        raised_dim_error = True
    assert raised_dim_error, "upsert with mismatched vector length must raise ValueError"

    # 3-5. happy-path upsert + search
    items = [
        VectorItem(
            id=f"id-{i}",
            vector=tuple(_unit_vector(dim, seed=i)),
            text=f"text {i}",
            metadata={"category": "doc" if i < 2 else "note", "n": i},  # noqa: PLR2004
        )
        for i in range(_ITEM_COUNT)
    ]
    await store.upsert(items)

    # Searching with the same vector as item-0 should put item-0 first.
    results = await store.search(items[0].vector, limit=_ITEM_COUNT)
    assert len(results) == _ITEM_COUNT, f"expected {_ITEM_COUNT} results, got {len(results)}"
    # Sorted by score descending, all in [0, 1]
    for prev, nxt in itertools.pairwise(results):
        assert prev.score >= nxt.score, f"results not sorted desc: {prev.score} before {nxt.score}"
    for r in results:
        assert 0.0 <= r.score <= 1.0, f"score out of range: {r.score}"
    assert results[0].id == "id-0", (
        f"top result must be the exact-match upsert, got {results[0].id!r}"
    )
    score_tolerance = 1e-3
    assert abs(results[0].score - 1.0) < score_tolerance, (
        f"exact-match score must be ~1.0, got {results[0].score}"
    )

    # 5. write-through: replace id-0 and search again
    replacement = VectorItem(
        id="id-0",
        vector=tuple(_unit_vector(dim, seed=99)),
        text="replaced",
        metadata={"category": "doc", "n": 0},
    )
    await store.upsert([replacement])
    after = await store.search(items[0].vector, limit=10)
    # No two results may share an id.
    seen_ids = [r.id for r in after]
    assert len(seen_ids) == len(set(seen_ids)), (
        f"upsert must replace prior records, but got duplicate ids: {seen_ids}"
    )

    # 7. metadata filtering
    filtered = await store.search(items[0].vector, limit=10, filter_metadata={"category": "doc"})
    for r in filtered:
        assert r.metadata.get("category") == "doc", (
            f"filter_metadata broken: returned {r.metadata!r}"
        )

    # 8. limit < 1 raises
    raised_limit_error = False
    try:
        await store.search(items[0].vector, limit=0)
    except ValueError:
        raised_limit_error = True
    assert raised_limit_error, "search(limit=0) must raise ValueError"

    # 6. delete: known + unknown ids
    deleted = await store.delete([item.id for item in items] + ["never-existed"])
    assert deleted == _ITEM_COUNT, (
        f"delete should report {_ITEM_COUNT} actual removals "
        f"(the {_ITEM_COUNT} we upserted), got {deleted}"
    )
    # Empty list returns 0
    assert await store.delete([]) == 0

    # 9. supports honesty
    assert store.supports("definitely-not-a-capability-2026") is False


def _unit_vector(dim: int, *, seed: int) -> list[float]:
    """Build a deterministic unit vector for conformance tests.

    Returns a one-hot-like vector with the seed-th component set high
    and a small uniform background, then L2-normalised so cosine
    similarity computations are stable across drivers.
    """
    raw = [0.01] * dim
    raw[seed % dim] = 1.0
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]
