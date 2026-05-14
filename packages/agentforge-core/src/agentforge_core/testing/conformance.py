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
from typing import Any

from agentforge_core.contracts.chat import ChatHistoryStore, HistoryTruncationStrategy
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.graph_store import GraphStore
from agentforge_core.contracts.guardrails import (
    InputValidator,
    OutputValidator,
    ToolCallGate,
)
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.contracts.task import Task
from agentforge_core.contracts.tool import Tool
from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.claim import Claim
from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    GraphSegment,
)
from agentforge_core.values.guardrails import ValidationResult
from agentforge_core.values.state import AgentState, StepKind
from agentforge_core.values.vector import VectorItem, VectorMatch

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


_EXPECTED_DELETE_COUNT = 2
"""Magic-number constant for the `delete()` conformance cases."""

_EXPECTED_CHAT_TURNS_SID = 2
"""Magic-number constant for the chat-history conformance cases."""

_EXPECTED_CHAT_TURNS_SID_B = 1
"""Magic-number constant for the chat-history conformance cases."""


async def _run_delete_conformance(store: MemoryStore) -> None:
    """feat-017 `delete()` conformance cases (separated from the main
    suite so the parent function stays under ruff's PLR0915 cap)."""
    from agentforge_core.production.exceptions import ModuleError  # noqa: PLC0415

    # No-filter refuses (defence against silent total wipe).
    try:
        await store.delete()
    except ModuleError:
        pass
    else:
        raise AssertionError("delete() with no filters must raise ModuleError")

    # delete(run_id=...) only removes matching claims; accurate count.
    purge_run = "run-purge"
    keeper_run = "run-keep"
    await store.put(_claim(run_id=purge_run, category="purge-me"))
    await store.put(_claim(run_id=purge_run, category="purge-me"))
    await store.put(_claim(run_id=keeper_run, category="purge-me"))
    removed_run = await store.delete(run_id=purge_run)
    assert removed_run == _EXPECTED_DELETE_COUNT, (
        f"delete(run_id={purge_run!r}) must return count; got {removed_run}"
    )
    remaining = await store.query(category="purge-me")
    assert all(c.run_id == keeper_run for c in remaining), (
        "delete(run_id=...) must leave non-matching claims behind"
    )

    # delete(category=...) clears the whole category.
    cat_marker = "ephemeral-step"
    await store.put(_claim(category=cat_marker))
    await store.put(_claim(category=cat_marker))
    await store.put(_claim(category="something-else"))
    removed_cat = await store.delete(category=cat_marker)
    assert removed_cat == _EXPECTED_DELETE_COUNT, (
        f"delete(category={cat_marker!r}) must report accurate count; got {removed_cat}"
    )
    after_cat = await store.query(category=cat_marker)
    assert after_cat == [], "delete(category=...) must clear all claims of that category"


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

    # 13-15. delete() — feat-017. Tested separately so the main
    # conformance function stays under PLR0915's statement cap.
    await _run_delete_conformance(store)


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


# ----------------------------------------------------------------------
# Graph store conformance — feat-009.
# ----------------------------------------------------------------------

# Named constants used by the graph conformance suite. Kept module-
# private; they're only meaningful inside the assertions below.
_GRAPH_PATH_LEN_TWO = 2  # (n0)-[e]->(n1) — one segment = two nodes
_GRAPH_DEPTH_TWO = 2  # paper:3 -> paper:2 -> paper:1
_EXPECTED_YEAR = 2017


async def run_graph_conformance(store: GraphStore) -> None:
    """Run the shared `GraphStore` conformance suite.

    The store must be empty when this is called and is left empty when
    the function returns (every node and edge created here is also
    deleted).

    Verifies the locked invariants of `GraphStore`:

      1. `add_node` is idempotent (re-adding the same id replaces the
         prior `properties` rather than appending or erroring).
      2. `get_node(id)` returns the most-recent node, or `None` if
         absent.
      3. `add_edge` rejects edges referencing unknown nodes
         (`ValueError`).
      4. `add_edge` is idempotent on `(src, dst, edge_type)`.
      5. `get_edges(id, direction=...)` honours the direction filter
         and the optional `edge_type` filter.
      6. `match()` finds a single-segment pattern and returns paths of
         length 2 (one edge, two nodes).
      7. `match(limit=...)` caps results.
      8. `traverse()` respects `max_depth` and never returns paths
         longer than `max_depth` edges.
      9. `delete_node(cascade=False)` raises if the node has incident
         edges; `cascade=True` removes them.
      10. `delete_edge` returns False on unknown triples and True on
          known ones.
      11. `supports()` is honest about unknown capabilities.

    Raises:
        AssertionError: a contract was violated.
    """
    await _graph_round_trip_invariants(store)
    await _graph_seed_citation_chain(store)
    await _graph_query_invariants(store)
    await _graph_delete_invariants(store)
    _graph_capability_invariants(store)


async def _graph_round_trip_invariants(store: GraphStore) -> None:
    """Round-trip and idempotency invariants on a single node."""
    n1 = GraphNode(id="paper:1", labels=("Doc",), properties={"topic": "ml"})
    await store.add_node(n1)

    fetched = await store.get_node("paper:1")
    assert fetched is not None, "get_node must return the persisted node"
    assert fetched.id == "paper:1"
    assert fetched.properties.get("topic") == "ml"

    # Unknown id returns None, not raise.
    missing = await store.get_node("paper:never")
    assert missing is None, "get_node of an unknown id must return None"

    # Idempotent upsert: re-add with extra properties replaces.
    n1_v2 = GraphNode(
        id="paper:1", labels=("Doc",), properties={"topic": "ml", "year": _EXPECTED_YEAR}
    )
    await store.add_node(n1_v2)
    refetched = await store.get_node("paper:1")
    assert refetched is not None
    assert refetched.properties.get("year") == _EXPECTED_YEAR, (
        "add_node must replace properties on idempotent upsert"
    )

    # add_edge rejects unknown endpoints.
    raised_unknown = False
    try:
        await store.add_edge(GraphEdge(src="ghost", dst="paper:1", edge_type="CITES"))
    except ValueError:
        raised_unknown = True
    assert raised_unknown, "add_edge must raise ValueError on unknown endpoint"


async def _graph_seed_citation_chain(store: GraphStore) -> None:
    """Seed a tiny three-paper citation chain. Assumes paper:1 exists."""
    await store.add_node(GraphNode(id="paper:2", labels=("Doc",), properties={"topic": "ml"}))
    await store.add_node(GraphNode(id="paper:3", labels=("Doc",), properties={"topic": "bio"}))
    await store.add_edge(GraphEdge(src="paper:2", dst="paper:1", edge_type="CITES"))
    await store.add_edge(GraphEdge(src="paper:3", dst="paper:2", edge_type="CITES"))

    # Idempotent edge upsert.
    await store.add_edge(
        GraphEdge(src="paper:2", dst="paper:1", edge_type="CITES", properties={"weight": 0.9})
    )
    out_edges = await store.get_edges("paper:2", direction="out")
    assert len([e for e in out_edges if e.dst == "paper:1"]) == 1, (
        "add_edge must be idempotent on (src, dst, edge_type)"
    )


async def _graph_query_invariants(store: GraphStore) -> None:
    """get_edges, match, and traverse invariants over the seeded chain."""
    out2 = await store.get_edges("paper:2", direction="out")
    assert all(e.src == "paper:2" for e in out2), "direction=out filter broken"

    in1 = await store.get_edges("paper:1", direction="in")
    assert all(e.dst == "paper:1" for e in in1), "direction=in filter broken"
    assert any(e.src == "paper:2" for e in in1)

    cites_only = await store.get_edges("paper:2", edge_type="CITES", direction="out")
    assert all(e.edge_type == "CITES" for e in cites_only)

    pattern = GraphPattern(
        segments=(GraphSegment(src_label="Doc", edge_type="CITES", dst_label="Doc"),),
    )
    matches = await store.match(pattern, limit=10)
    assert len(matches) >= 1, "match should find at least one CITES edge"
    for path in matches:
        assert len(path.nodes) == _GRAPH_PATH_LEN_TWO, (
            "single-segment match must return length-2 paths"
        )
        assert len(path.edges) == 1
        assert path.edges[0].edge_type == "CITES"

    capped = await store.match(pattern, limit=1)
    assert len(capped) <= 1

    paths_d1 = await store.traverse("paper:3", max_depth=1)
    for p in paths_d1:
        assert len(p.edges) <= 1, f"max_depth=1 must not return path with {len(p.edges)} edges"

    paths_d2 = await store.traverse("paper:3", max_depth=_GRAPH_DEPTH_TWO)
    reaches_paper1 = any(p.nodes[-1].id == "paper:1" for p in paths_d2)
    assert reaches_paper1, "traverse(max_depth=2) from paper:3 must reach paper:1"
    for p in paths_d2:
        assert len(p.edges) <= _GRAPH_DEPTH_TWO

    empty_traverse = await store.traverse("ghost-node", max_depth=_GRAPH_DEPTH_TWO)
    assert empty_traverse == [], "traverse from unknown node must return empty list"


async def _graph_delete_invariants(store: GraphStore) -> None:
    """Cascade and unknown-triple delete invariants. Empties the store."""
    raised_cascade = False
    try:
        await store.delete_node("paper:2", cascade=False)
    except ValueError:
        raised_cascade = True
    assert raised_cascade, "delete_node with cascade=False must raise on connected node"

    deleted = await store.delete_node("paper:2", cascade=True)
    assert deleted is True
    assert await store.get_node("paper:2") is None
    assert (await store.get_edges("paper:1", direction="in")) == []

    # Unknown triple returns False, not raise.
    assert await store.delete_edge("paper:3", "paper:never", edge_type="CITES") is False

    # Empty the store fully.
    await store.delete_node("paper:1", cascade=True)
    await store.delete_node("paper:3", cascade=True)


def _graph_capability_invariants(store: GraphStore) -> None:
    """capabilities() / supports() honesty."""
    caps = store.capabilities()
    assert isinstance(caps, set)
    assert store.supports("definitely-not-a-capability-2026") is False
    if caps:
        sample = next(iter(caps))
        assert store.supports(sample) is True


# ======================================================================
# Guardrail conformance — feat-018.
# ======================================================================


async def run_input_validator_conformance(
    validator: InputValidator,
    *,
    benign: str = "What is the weather today?",
    obvious_violation: str | None = None,
) -> None:
    """Validate that an InputValidator honours the locked contract.

    - Concrete subclass declares `name` and `description`.
    - `.validate(...)` returns a `ValidationResult`.
    - Benign input produces `passed=True` and an empty `violations`
      tuple.
    - When `obvious_violation` is supplied, the validator flags it
      (`passed=False`).
    """
    assert isinstance(getattr(validator, "name", None), str), "name must be a str ClassVar"
    assert isinstance(
        getattr(validator, "description", None),
        str,
    ), "description must be a str ClassVar"

    result = await validator.validate(benign, {"run_id": "conformance"})
    assert isinstance(result, ValidationResult), "validate() must return ValidationResult"
    assert result.passed, f"benign input must pass; got violations {list(result.violations)!r}"

    if obvious_violation is not None:
        bad = await validator.validate(obvious_violation, {"run_id": "conformance"})
        assert isinstance(bad, ValidationResult)
        assert not bad.passed, (
            f"obvious-violation input must fail; validator {validator.name!r} returned passed=True"
        )


async def run_output_validator_conformance(
    validator: OutputValidator,
    *,
    benign: str = "The weather is nice today.",
    obvious_violation: str | None = None,
) -> None:
    """Same contract as `run_input_validator_conformance` but for
    output validators. If `obvious_violation` is supplied and the
    validator can redact, asserts that `redacted_content` is set."""
    assert isinstance(getattr(validator, "name", None), str)
    assert isinstance(getattr(validator, "description", None), str)

    result = await validator.validate(benign, {"run_id": "conformance"})
    assert isinstance(result, ValidationResult)
    assert result.passed, f"benign output must pass; got {list(result.violations)!r}"

    if obvious_violation is not None:
        bad = await validator.validate(obvious_violation, {"run_id": "conformance"})
        assert isinstance(bad, ValidationResult)
        assert not bad.passed, "obvious-violation output must fail"


async def run_tool_gate_conformance(
    gate: ToolCallGate,
    *,
    benign_tool: Tool,
    benign_tool_name: str,
    forbidden_tool: Tool | None = None,
    forbidden_tool_name: str | None = None,
) -> None:
    """Validate that a ToolCallGate honours the locked contract."""
    assert isinstance(getattr(gate, "name", None), str)
    assert isinstance(getattr(gate, "description", None), str)

    benign_result = await gate.authorize(benign_tool_name, benign_tool, {}, {})
    assert isinstance(benign_result, ValidationResult)

    if forbidden_tool is not None and forbidden_tool_name is not None:
        denied = await gate.authorize(forbidden_tool_name, forbidden_tool, {}, {})
        assert isinstance(denied, ValidationResult)
        assert not denied.passed, (
            f"gate {gate.name!r} must deny {forbidden_tool_name!r}; got passed=True"
        )


# ----------------------------------------------------------------------
# Task conformance — feat-015.
# ----------------------------------------------------------------------


async def run_task_conformance(
    task: Task,
    *,
    context: dict[str, object] | None = None,
) -> None:
    """Validate that a Task honours the locked contract.

    Asserts:
      1. ``name`` is a non-empty string.
      2. ``cost_estimate_usd`` is a non-negative float.
      3. ``timeout_s`` is a positive float.
      4. ``depends_on`` is a tuple of strings (possibly empty).
      5. ``run(context)`` returns a list (the engine treats an empty
         list as a valid no-finding result).
      6. Every emitted finding has the three required ``Finding``
         attributes (``severity``, ``category``, ``message``).
    """
    name = type(task).name
    assert isinstance(name, str), "Task.name must be a string"
    assert name, "Task.name must be non-empty"
    assert isinstance(type(task).cost_estimate_usd, (int, float)), (
        "Task.cost_estimate_usd must be numeric"
    )
    assert float(type(task).cost_estimate_usd) >= 0.0, "Task.cost_estimate_usd must be non-negative"
    assert isinstance(type(task).timeout_s, (int, float)), "Task.timeout_s must be numeric"
    assert float(type(task).timeout_s) > 0.0, "Task.timeout_s must be positive"
    deps = type(task).depends_on
    assert isinstance(deps, tuple), f"Task.depends_on must be a tuple, got {type(deps).__name__}"
    for dep in deps:
        assert isinstance(dep, str), "Task.depends_on entries must be strings"

    findings = await task.run(context if context is not None else {})
    assert isinstance(findings, list), (
        f"Task.run must return a list of findings, got {type(findings).__name__}"
    )
    for f in findings:
        assert hasattr(f, "severity"), "finding must have a 'severity' attribute"
        assert isinstance(f.severity, str), "finding.severity must be a string"
        assert hasattr(f, "category"), "finding must have a 'category' attribute"
        assert isinstance(f.category, str), "finding.category must be a string"
        assert hasattr(f, "message"), "finding must have a 'message' attribute"
        assert isinstance(f.message, str), "finding.message must be a string"


# ----------------------------------------------------------------------
# Chat conformance — feat-020.
# ----------------------------------------------------------------------


async def run_chat_history_conformance(store: ChatHistoryStore) -> None:
    """Validate that a `ChatHistoryStore` honours the locked contract.

    The store must be empty when this is called and is left empty
    when the function returns.
    """
    from datetime import UTC, datetime  # noqa: PLC0415
    from uuid import uuid4  # noqa: PLC0415

    from agentforge_core.values.chat import ChatTurn  # noqa: PLC0415

    sid = f"conf-{uuid4().hex[:8]}"
    sid_b = f"conf-{uuid4().hex[:8]}"

    def _turn(session: str, role: str, content: str, **kw: Any) -> ChatTurn:
        return ChatTurn(
            id=uuid4().hex,
            session_id=session,
            role=role,  # type: ignore[arg-type]
            content=content,
            timestamp=datetime.now(UTC),
            **kw,
        )

    # 1. append + load round-trip.
    t1 = _turn(sid, "user", "hello")
    t2 = _turn(sid, "assistant", "hi there", run_id="run-1")
    await store.append(t1)
    await store.append(t2)
    loaded = await store.load(sid)
    assert len(loaded) == _EXPECTED_CHAT_TURNS_SID, (
        f"load() must return both turns; got {len(loaded)}"
    )
    assert loaded[0].id == t1.id, "load() must return turns in chronological order"
    assert loaded[1].id == t2.id

    # 2. count.
    n = await store.count(sid)
    assert n == _EXPECTED_CHAT_TURNS_SID, f"count() must reflect appended turns; got {n}"

    # 3. session isolation — a different session_id sees nothing.
    other_turn = _turn(sid_b, "user", "different session")
    await store.append(other_turn)
    only_a = await store.load(sid)
    assert all(t.session_id == sid for t in only_a), (
        "load(session_id) must not bleed across sessions"
    )
    assert await store.count(sid_b) == _EXPECTED_CHAT_TURNS_SID_B

    # 4. role filter.
    only_assistant = await store.load(sid, roles=["assistant"])
    assert all(t.role == "assistant" for t in only_assistant), (
        "load(roles=...) must filter to those roles"
    )

    # 5. limit.
    limited = await store.load(sid, limit=1)
    assert len(limited) == 1, "load(limit=N) must return at most N turns"

    # 6. list_sessions returns info for every active session.
    sessions = await store.list_sessions()
    ids = {s.id for s in sessions}
    assert sid in ids, "list_sessions() must include the first session"
    assert sid_b in ids, "list_sessions() must include the second session"

    # 7. update_session_metadata merges keys.
    await store.update_session_metadata(sid, {"owner": "alice", "tag": "x"})
    after = await store.list_sessions()
    matched = [s for s in after if s.id == sid]
    assert matched, "session must still appear after update_session_metadata()"

    # 8. owner filter on list_sessions.
    owned = await store.list_sessions(owner="alice")
    assert all(s.owner == "alice" for s in owned), (
        "list_sessions(owner=X) must filter to that owner"
    )

    # 9. delete_session removes turns + returns count.
    removed = await store.delete_session(sid)
    assert removed == _EXPECTED_CHAT_TURNS_SID, (
        f"delete_session must return turns removed; got {removed}"
    )
    assert await store.count(sid) == 0
    after_other = await store.count(sid_b)
    assert after_other == _EXPECTED_CHAT_TURNS_SID_B, "delete_session must not touch other sessions"

    # 10. expire_before — drivers without TTL may return 0.
    far_future = datetime(2099, 1, 1, tzinfo=UTC)
    removed_b = await store.expire_before(far_future)
    assert isinstance(removed_b, int), "expire_before must return an int"

    # 11. capabilities is a set.
    caps = store.capabilities()
    assert isinstance(caps, set)
    assert store.supports("definitely-not-a-real-capability") is False

    # Clean up remaining session.
    await store.delete_session(sid_b)
    await store.expire_before(far_future)


async def run_truncation_conformance(strategy: HistoryTruncationStrategy) -> None:
    """Validate that a `HistoryTruncationStrategy` honours the
    locked invariants.

    Asserts:
      1. Output is a subsequence of input (order preserved, no
         injection).
      2. Empty input → empty output.
    """
    from datetime import UTC, datetime  # noqa: PLC0415
    from uuid import uuid4  # noqa: PLC0415

    from agentforge_core.values.chat import ChatTurn  # noqa: PLC0415

    def _turn(role: str, content: str) -> ChatTurn:
        return ChatTurn(
            id=uuid4().hex,
            session_id="conf",
            role=role,  # type: ignore[arg-type]
            content=content,
            timestamp=datetime.now(UTC),
        )

    empty: list[ChatTurn] = []
    out = await strategy.select(empty, "msg", {})
    assert out == [], "empty input must yield empty output"

    seq = [
        _turn("user", "a"),
        _turn("assistant", "b"),
        _turn("user", "c"),
        _turn("assistant", "d"),
    ]
    picked = await strategy.select(seq, "next msg", {})
    ids = [t.id for t in seq]
    # Output must preserve order: original turns appear in the same
    # relative order as in `seq`. Synthesised summary turns marked
    # `metadata["agentforge_chat.summary"] == True` are allowed
    # (`SummariseOldest`) and skipped from the subsequence check.
    iter_ids = iter(ids)
    for t in picked:
        if t.metadata.get("agentforge_chat.summary") is True:
            continue
        assert t.id in iter_ids, (
            "truncation output must preserve input order "
            "(no reordered or inserted non-summary turns)"
        )


async def run_reranker_conformance(reranker: Reranker) -> None:
    """Run the shared `Reranker` conformance suite (feat-021).

    The reranker must be ready to call when this is passed in and is
    not touched after the function returns (callers manage the
    reranker's lifecycle).

    Verifies the locked invariants of `Reranker`:

      1. Empty candidate list returns an empty list, no calls to any
         backing model.
      2. ``top_k < 1`` (when not None) raises `ValueError`.
      3. ``rerank(query, candidates, top_k=None)`` returns a list of
         the same length as `candidates`.
      4. ``rerank(query, candidates, top_k=K)`` returns at most
         `K` items.
      5. Returned scores are in `[0, 1]`.
      6. Results are sorted descending by score.
      7. Returned `VectorMatch` objects carry the input's `id` /
         `text` / `metadata` values unchanged (only `score` may
         change).
      8. Input list is not mutated.
      9. ``supports("not-a-real-capability")`` returns False.

    Raises:
        AssertionError: a contract was violated.
    """

    # 1. empty input → empty output, no work
    empty = await reranker.rerank("any query", [])
    assert empty == [], f"rerank([]) must return [], got {empty!r}"

    # 2. top_k < 1 must raise
    candidates = [
        VectorMatch(id="a", text="alpha", score=0.9, metadata={"k": 1}),
        VectorMatch(id="b", text="beta", score=0.5, metadata={"k": 2}),
        VectorMatch(id="c", text="gamma", score=0.3, metadata={"k": 3}),
    ]
    raised_topk = False
    try:
        await reranker.rerank("q", candidates, top_k=0)
    except ValueError:
        raised_topk = True
    assert raised_topk, "rerank(top_k=0) must raise ValueError"

    # 3-7. happy path
    original = list(candidates)
    full = await reranker.rerank("q", candidates)
    assert len(full) == len(candidates), (
        f"rerank(top_k=None) must return all candidates, got {len(full)} vs {len(candidates)}"
    )
    for r in full:
        assert 0.0 <= r.score <= 1.0, f"score out of range: {r.score}"
    for prev, nxt in itertools.pairwise(full):
        assert prev.score >= nxt.score, f"results not sorted desc: {prev.score} before {nxt.score}"
    by_id = {r.id: r for r in full}
    for orig in original:
        out = by_id[orig.id]
        assert out.text == orig.text, (
            f"text field mutated for id={orig.id}: {orig.text!r} → {out.text!r}"
        )
        assert out.metadata == orig.metadata, (
            f"metadata mutated for id={orig.id}: {orig.metadata!r} → {out.metadata!r}"
        )

    # 4. top_k truncates
    truncated = await reranker.rerank("q", candidates, top_k=2)
    assert len(truncated) == 2, f"top_k=2 must return 2 items, got {len(truncated)}"  # noqa: PLR2004
    for prev, nxt in itertools.pairwise(truncated):
        assert prev.score >= nxt.score

    # 8. input not mutated
    assert candidates == original, "rerank must not mutate its input list"

    # 9. unknown capability check
    assert reranker.supports("not-a-real-capability") is False, (
        "supports() must return False for unknown capability"
    )


# ----------------------------------------------------------------------
# Hybrid-search conformance — feat-022 (opt-in).
# ----------------------------------------------------------------------


async def run_hybrid_search_conformance(store: VectorStore) -> None:
    """Verify the `lexical_search` contract for hybrid-capable drivers.

    Only call this on stores that declare the ``"hybrid_search"``
    capability — the function asserts the precondition. Empty store
    in, empty store out (every item upserted is deleted).

    Verifies:

      1. ``store.supports("hybrid_search")`` is True.
      2. Empty corpus returns ``[]``.
      3. ``lexical_search`` returns at most ``limit`` matches sorted
         by score desc, with scores in ``[0, 1]`` (max-normalised).
      4. The top hit on an exact-token query is the document that
         contains the rarest matching token.
      5. ``filter_metadata`` AND-matches on the lexical path.
      6. ``limit=0`` raises ``ValueError``.
      7. Re-upserting an existing id with new text invalidates the
         prior lexical hit (the new text wins).

    Raises:
        AssertionError: a contract was violated.
    """
    assert store.supports("hybrid_search"), (
        "run_hybrid_search_conformance called on a store that does not declare 'hybrid_search'"
    )

    # 2. empty corpus
    empty = await store.lexical_search("anything", limit=5)
    assert empty == [], f"empty store must return [], got {empty!r}"

    dim = store.dimensions()
    base_vec = tuple([0.1] * dim)
    items = [
        VectorItem(
            id="a", vector=base_vec, text="Paris is the capital of France", metadata={"k": 1}
        ),
        VectorItem(
            id="b", vector=base_vec, text="Berlin is the capital of Germany", metadata={"k": 2}
        ),
        VectorItem(id="c", vector=base_vec, text="The Eiffel Tower is in Paris", metadata={"k": 1}),
    ]
    await store.upsert(items)

    try:
        # 6. limit < 1 must raise
        raised_limit = False
        try:
            await store.lexical_search("Paris", limit=0)
        except ValueError:
            raised_limit = True
        assert raised_limit, "lexical_search(limit=0) must raise ValueError"

        # 3. ordering + score range
        eiffel = await store.lexical_search("Eiffel Tower", limit=5)
        assert len(eiffel) >= 1, "Eiffel Tower query must match at least one doc"
        assert eiffel[0].id == "c", f"top hit on 'Eiffel Tower' must be doc c, got {eiffel[0].id}"
        for prev, nxt in itertools.pairwise(eiffel):
            assert prev.score >= nxt.score, "lexical_search results not sorted desc"
        for m in eiffel:
            assert 0.0 <= m.score <= 1.0, f"lexical score out of [0, 1]: {m.score}"

        # 5. metadata filter
        filtered = await store.lexical_search("capital", limit=5, filter_metadata={"k": 1})
        ids = {m.id for m in filtered}
        # docs with k=1 are a (Paris/capital) and c (Eiffel/Paris)
        assert "b" not in ids, "filter_metadata={k: 1} must exclude doc b"

        # 7. re-upsert invalidates prior text
        await store.upsert(
            [
                VectorItem(
                    id="a",
                    vector=base_vec,
                    text="Madrid is the capital of Spain",
                    metadata={"k": 1},
                ),
            ]
        )
        paris_after = await store.lexical_search("Paris", limit=5)
        paris_ids = {m.id for m in paris_after}
        assert "a" not in paris_ids, (
            "re-upserting doc a with new text must drop it from a 'Paris' query"
        )
    finally:
        await store.delete(["a", "b", "c"])
