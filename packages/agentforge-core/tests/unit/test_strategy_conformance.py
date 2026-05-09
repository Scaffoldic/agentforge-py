"""Unit tests for `run_strategy_conformance`."""

from __future__ import annotations

import pytest
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.testing import run_strategy_conformance
from agentforge_core.values.state import AgentState, Step


class _GoodStrategy(ReasoningStrategy):
    """Conformant: returns same state, appends a valid step."""

    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="observe", content="ok"))
        return state


class _ReturnsDifferentState(ReasoningStrategy):
    """Non-conformant: returns a fresh AgentState instead of mutating."""

    async def run(self, state: AgentState) -> AgentState:
        return AgentState(
            run_id=state.run_id,
            task=state.task,
            steps=[Step(iteration=0, kind="observe", content="ok")],
        )


class _NoSteps(ReasoningStrategy):
    """Non-conformant: never appends a step."""

    async def run(self, state: AgentState) -> AgentState:
        return state


class _NonMonotonicIteration(ReasoningStrategy):
    """Non-conformant: step.iteration goes backwards."""

    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=5, kind="think", content="a"))
        state.steps.append(Step(iteration=2, kind="observe", content="b"))
        return state


def _state_factory() -> AgentState:
    return AgentState(run_id="r", task="t")


@pytest.mark.asyncio
async def test_good_strategy_passes() -> None:
    await run_strategy_conformance(_GoodStrategy(), state_factory=_state_factory)


@pytest.mark.asyncio
async def test_strategy_returning_different_instance_fails() -> None:
    with pytest.raises(AssertionError, match="same AgentState instance"):
        await run_strategy_conformance(_ReturnsDifferentState(), state_factory=_state_factory)


@pytest.mark.asyncio
async def test_strategy_emitting_no_steps_fails() -> None:
    with pytest.raises(AssertionError, match="at least one Step"):
        await run_strategy_conformance(_NoSteps(), state_factory=_state_factory)


@pytest.mark.asyncio
async def test_non_monotonic_iteration_fails() -> None:
    with pytest.raises(AssertionError, match="monotonically non-decreasing"):
        await run_strategy_conformance(_NonMonotonicIteration(), state_factory=_state_factory)


@pytest.mark.asyncio
async def test_pre_run_hook_invoked() -> None:
    seen: list[str] = []

    def hook(state: AgentState) -> None:
        seen.append(state.run_id)

    await run_strategy_conformance(_GoodStrategy(), state_factory=_state_factory, pre_run=hook)
    assert seen == ["r"]


@pytest.mark.asyncio
async def test_pre_run_async_hook_awaited() -> None:
    seen: list[str] = []

    async def hook(state: AgentState) -> None:
        seen.append(state.run_id)

    await run_strategy_conformance(_GoodStrategy(), state_factory=_state_factory, pre_run=hook)
    assert seen == ["r"]
