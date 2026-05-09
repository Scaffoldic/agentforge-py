"""Unit tests for the `ReasoningStrategy` ABC."""

from __future__ import annotations

import pytest
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.state import AgentState, Step


def test_reasoning_strategy_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError, match="abstract"):
        ReasoningStrategy()  # type: ignore[abstract]


class _NoOpStrategy(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="system", content="no-op strategy ran"))
        return state


@pytest.mark.asyncio
async def test_minimal_subclass_works() -> None:
    strategy = _NoOpStrategy()
    state = AgentState(run_id="r1", task="t")
    result = await strategy.run(state)
    assert result is state
    assert len(result.steps) == 1
    assert result.steps[0].kind == "system"
