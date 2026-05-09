"""Unit tests for `StrategyBase` and `get_runtime`."""

from __future__ import annotations

import pytest
from agentforge import InMemoryStore
from agentforge._testing import FakeLLMClient, echo_response
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge.strategies import StrategyBase, get_runtime
from agentforge_core import BudgetExceeded, BudgetPolicy
from agentforge_core.values.messages import Message
from agentforge_core.values.state import AgentState


class _DemoStrategy(StrategyBase):
    """Test-only strategy: one LLM call via `_call_llm`, no tools."""

    async def run(self, state: AgentState) -> AgentState:
        await self._call_llm(
            state,
            iteration=0,
            system="sys",
            messages=[Message(role="user", content=state.task)],
        )
        return state


def _state_with_runtime(llm: FakeLLMClient | None = None) -> AgentState:
    rt = RuntimeContext(
        llm=llm if llm is not None else FakeLLMClient(),
        tools=(),
        memory=InMemoryStore(),
        budget=BudgetPolicy(usd=1.0, max_iterations=5),
    )
    return AgentState(run_id="r1", task="hi", metadata={RUNTIME_KEY: rt})


# ---- get_runtime ----


def test_get_runtime_returns_bound_context() -> None:
    state = _state_with_runtime()
    rt = get_runtime(state)
    assert isinstance(rt, RuntimeContext)


def test_get_runtime_raises_when_unbound() -> None:
    state = AgentState(run_id="r", task="t")
    with pytest.raises(RuntimeError, match="no RuntimeContext"):
        get_runtime(state)


def test_get_runtime_raises_when_wrong_type() -> None:
    state = AgentState(run_id="r", task="t", metadata={RUNTIME_KEY: "not a context"})
    with pytest.raises(TypeError, match="not a RuntimeContext"):
        get_runtime(state)


# ---- StrategyBase ----


def test_strategybase_is_abstract() -> None:
    with pytest.raises(TypeError, match="abstract"):
        StrategyBase()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_call_llm_records_step_and_commits_cost() -> None:
    fake = FakeLLMClient(
        responses=[echo_response(content="answer", input_tokens=10, output_tokens=5, cost_usd=0.01)]
    )
    state = _state_with_runtime(llm=fake)
    strategy = _DemoStrategy()

    result = await strategy.run(state)

    assert result is state
    assert len(state.steps) == 1
    step = state.steps[0]
    assert step.kind == "think"
    assert step.content == "answer"
    assert step.tokens_in == 10
    assert step.tokens_out == 5
    assert step.cost_usd == pytest.approx(0.01)

    rt = get_runtime(state)
    assert rt.budget.spent_usd == pytest.approx(0.01)
    assert rt.budget.consumed_tokens == 15
    assert rt.budget.iteration == 1


@pytest.mark.asyncio
async def test_call_llm_checks_guardrails_first() -> None:
    """If budget is exhausted, _call_llm must not invoke the LLM."""
    fake = FakeLLMClient(responses=[echo_response()])
    rt = RuntimeContext(
        llm=fake,
        tools=(),
        memory=InMemoryStore(),
        budget=BudgetPolicy(usd=0.0),  # zero budget — already at cap
    )
    rt.budget.commit(0.001)  # nudge over
    state = AgentState(run_id="r", task="t", metadata={RUNTIME_KEY: rt})
    strategy = _DemoStrategy()

    with pytest.raises(BudgetExceeded):
        await strategy.run(state)
    assert fake.call_count == 0  # never reached the LLM


@pytest.mark.asyncio
async def test_record_step_appends_to_state() -> None:
    state = _state_with_runtime()
    strategy = _DemoStrategy()
    step = strategy._record_step(state, iteration=2, kind="observe", content="ok")
    assert state.steps[-1] is step
    assert step.iteration == 2
    assert step.kind == "observe"


def test_check_guardrails_calls_budget_check() -> None:
    state = _state_with_runtime()

    class _S(StrategyBase):
        async def run(self, state: AgentState) -> AgentState:
            return state

    s = _S()
    s._check_guardrails(state)
    rt = get_runtime(state)
    assert rt.budget.iteration == 0  # check doesn't increment
