"""Unit tests for `TreeOfThoughts`."""

from __future__ import annotations

import pytest
from agentforge import InMemoryStore
from agentforge._testing import FakeLLMClient
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge.strategies import TreeOfThoughts
from agentforge_core import BudgetPolicy
from agentforge_core.resolver import Resolver
from agentforge_core.values.messages import LLMResponse, TokenUsage
from agentforge_core.values.state import AgentState


def _resp(content: str = "", *, cost: float = 0.001) -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=5, output_tokens=3),
        cost_usd=cost,
        model="fake",
        provider="fake",
    )


def _state(fake: FakeLLMClient, *, budget: BudgetPolicy | None = None) -> AgentState:
    rt = RuntimeContext(
        llm=fake,
        tools=(),
        memory=InMemoryStore(),
        budget=budget if budget is not None else BudgetPolicy(usd=2.0, max_iterations=20),
    )
    return AgentState(run_id="r1", task="solve x", metadata={RUNTIME_KEY: rt})


def _thoughts(branch_factor: int) -> str:
    """Build a valid `_ThoughtList` JSON for the given branch_factor."""
    items = [f'{{"id": "t{i}", "content": "thought {i}"}}' for i in range(1, branch_factor + 1)]
    return '{"thoughts": [' + ", ".join(items) + "]}"


def _scores(scores_by_id: dict[str, float]) -> str:
    items = [
        f'{{"branch_id": "{k}", "score": {v}, "reasoning": "..."}}' for k, v in scores_by_id.items()
    ]
    return '{"scores": [' + ", ".join(items) + "]}"


# ---- Constructor validation ----


def test_constructor_validates_branch_factor() -> None:
    with pytest.raises(ValueError, match="branch_factor"):
        TreeOfThoughts(branch_factor=0)


def test_constructor_validates_depth() -> None:
    with pytest.raises(ValueError, match="depth"):
        TreeOfThoughts(depth=0)


def test_constructor_validates_score_threshold() -> None:
    with pytest.raises(ValueError, match="score_threshold"):
        TreeOfThoughts(score_threshold=1.5)


def test_constructor_validates_scorer() -> None:
    with pytest.raises(ValueError, match="scorer"):
        TreeOfThoughts(scorer="bogus")  # type: ignore[arg-type]


def test_constructor_validates_beam_width() -> None:
    with pytest.raises(ValueError, match="beam_width"):
        TreeOfThoughts(beam_width=0)


def test_registered_under_strategies_tot() -> None:
    cls = Resolver.global_().resolve("strategies", "tot")
    assert cls is TreeOfThoughts


# ---- Single-level happy path ----


@pytest.mark.asyncio
async def test_single_depth_with_three_branches() -> None:
    """depth=1, branch_factor=3 → 1 generate + 1 score + 1 synthesize."""
    fake = FakeLLMClient(
        responses=[
            _resp(_thoughts(3)),
            _resp(_scores({"t1": 0.9, "t2": 0.4, "t3": 0.7})),
            _resp("Final answer based on best branch."),
        ]
    )
    state = _state(fake)
    await TreeOfThoughts(branch_factor=3, depth=1, score_threshold=0.5).run(state)

    assert fake.call_count == 3
    branches = [s for s in state.steps if s.kind == "branch"]
    assert len(branches) == 3
    synth = [s for s in state.steps if s.kind == "synthesize"]
    assert len(synth) == 1


# ---- Beam width pruning ----


@pytest.mark.asyncio
async def test_beam_width_keeps_top_k() -> None:
    """beam_width=1 — only highest-scored branch survives the level."""
    fake = FakeLLMClient(
        responses=[
            _resp(_thoughts(3)),
            _resp(_scores({"t1": 0.9, "t2": 0.4, "t3": 0.7})),
            # depth=2: only t1 should expand
            _resp(_thoughts(2)),  # at child level: 2 candidates
            _resp(_scores({"t1": 0.85, "t2": 0.4})),
            _resp("done"),
        ]
    )
    state = _state(fake)
    await TreeOfThoughts(branch_factor=3, depth=2, score_threshold=0.5, beam_width=1).run(state)
    # 3 (level-1 branches) + 2 (level-2 branches under t1) = 5
    branches = [s for s in state.steps if s.kind == "branch"]
    assert len(branches) == 5


# ---- Score-threshold pruning ----


@pytest.mark.asyncio
async def test_score_threshold_prunes_weak_branches() -> None:
    """All branches below threshold → no survivors → synthesise from root."""
    fake = FakeLLMClient(
        responses=[
            _resp(_thoughts(3)),
            _resp(_scores({"t1": 0.1, "t2": 0.2, "t3": 0.05})),
            _resp("synthesis from root"),
        ]
    )
    state = _state(fake)
    await TreeOfThoughts(branch_factor=3, depth=2, score_threshold=0.5).run(state)
    # No level-2 expansion happens because no level-1 survivors
    assert fake.call_count == 3


# ---- Graceful degradation on budget ----


@pytest.mark.asyncio
async def test_budget_aware_graceful_degradation() -> None:
    """Tight budget — strategy synthesises with what it has rather
    than tripping BudgetExceeded mid-search."""
    expensive = _resp(_thoughts(2), cost=0.4)
    fake = FakeLLMClient(
        responses=[
            expensive,
            _resp(_scores({"t1": 0.9, "t2": 0.8}), cost=0.4),
            _resp("partial synthesis", cost=0.05),
        ]
    )
    state = _state(fake, budget=BudgetPolicy(usd=1.0, max_iterations=20))
    await TreeOfThoughts(branch_factor=2, depth=3, score_threshold=0.5).run(state)
    # Depth=3 is requested but budget runs out after the first level;
    # strategy synthesises what it has rather than crashing.
    synth = [s for s in state.steps if s.kind == "synthesize"]
    assert len(synth) == 1


# ---- Parse-error fallback ----


@pytest.mark.asyncio
async def test_invalid_thoughts_json_yields_no_branches() -> None:
    """Generation parse failure → no branches at this level; synthesise root."""
    fake = FakeLLMClient(
        responses=[
            _resp("not valid JSON for thoughts"),
            _resp("synthesis"),
        ]
    )
    state = _state(fake)
    await TreeOfThoughts(branch_factor=2, depth=1).run(state)
    assert fake.call_count == 2
    branches = [s for s in state.steps if s.kind == "branch"]
    assert branches == []


@pytest.mark.asyncio
async def test_invalid_scores_json_defaults_neutral() -> None:
    """Score parse failure → all candidates default to 0.5 (logged warning)."""
    fake = FakeLLMClient(
        responses=[
            _resp(_thoughts(2)),
            _resp("scores parse error"),
            _resp("synthesis"),
        ]
    )
    state = _state(fake)
    # threshold=0.5 with default-0.5 scores — exactly threshold; survives
    await TreeOfThoughts(branch_factor=2, depth=1, score_threshold=0.5).run(state)
    assert fake.call_count == 3


# ---- Code-fence stripping ----


@pytest.mark.asyncio
async def test_strips_code_fences_from_generation() -> None:
    fake = FakeLLMClient(
        responses=[
            _resp("```json\n" + _thoughts(2) + "\n```"),
            _resp("```json\n" + _scores({"t1": 0.9, "t2": 0.7}) + "\n```"),
            _resp("done"),
        ]
    )
    state = _state(fake)
    await TreeOfThoughts(branch_factor=2, depth=1).run(state)
    assert fake.call_count == 3


# ---- scorer="judge" alias ----


@pytest.mark.asyncio
async def test_scorer_judge_falls_back_to_self() -> None:
    """scorer="judge" deferred to feat-006; for v0.1 it behaves like 'self'."""
    fake = FakeLLMClient(
        responses=[
            _resp(_thoughts(2)),
            _resp(_scores({"t1": 0.9, "t2": 0.6})),
            _resp("done"),
        ]
    )
    state = _state(fake)
    await TreeOfThoughts(branch_factor=2, depth=1, scorer="judge").run(state)
    assert fake.call_count == 3
