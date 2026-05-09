"""Property tests — budget invariants hold across all four strategies.

For every shipped reasoning strategy, regardless of the LLM responses
(or per-call cost), the run must either:

  - Terminate cleanly with `spent_usd <= cap`, or
  - Raise `BudgetExceeded` / `GuardrailViolation` (which the runtime
    converts into a `finish_reason` at the Agent level), with
    `spent_usd <= cap + max_call_cost` (one over-spend is allowed at
    the moment of commit; subsequent calls are blocked by `check`).

Every shipped strategy honours the same invariant — this test
fixture exercises ReAct, Plan-Execute, ToT, and Multi-Agent over a
range of budgets and call costs.
"""

from __future__ import annotations

import pytest
from agentforge import InMemoryStore
from agentforge._testing import FakeLLMClient
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge.strategies import (
    MultiAgentSupervisor,
    PlanExecuteLoop,
    ReActLoop,
    TreeOfThoughts,
)
from agentforge_core import BudgetPolicy
from agentforge_core.production.exceptions import BudgetExceeded, GuardrailViolation
from agentforge_core.values.messages import LLMResponse, TokenUsage
from agentforge_core.values.state import AgentState
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


def _resp(content: str = "", *, cost: float = 0.001) -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=5, output_tokens=3),
        cost_usd=cost,
        model="fake",
        provider="fake",
    )


def _make_state(fake: FakeLLMClient, *, budget: BudgetPolicy) -> tuple[AgentState, RuntimeContext]:
    rt = RuntimeContext(
        llm=fake,
        tools=(),
        memory=InMemoryStore(),
        budget=budget,
    )
    state = AgentState(run_id="prop-r", task="solve", metadata={RUNTIME_KEY: rt})
    return state, rt


# Precanned valid JSON outputs — random costs, fixed-shape content
# so the strategies parse successfully and exercise the full path.
def _react_responses(costs: list[float]) -> list[LLMResponse]:
    return [_resp("done", cost=c) for c in costs]


def _plan_responses(costs: list[float]) -> list[LLMResponse]:
    plan_json = (
        '{"steps": [{"id": "s1", "description": "think", '
        '"tool": null, "arguments": {}, "depends_on": []}]}'
    )
    out: list[LLMResponse] = [_resp(plan_json, cost=costs[0] if costs else 0.001)]
    out.append(_resp("step1 thought", cost=costs[1] if len(costs) > 1 else 0.001))
    out.append(_resp("done", cost=costs[2] if len(costs) > 2 else 0.001))
    return out


def _tot_responses(costs: list[float]) -> list[LLMResponse]:
    thoughts = '{"thoughts": [{"id": "t1", "content": "x"}]}'
    scores = '{"scores": [{"branch_id": "t1", "score": 0.8, "reasoning": ""}]}'
    return [
        _resp(thoughts, cost=costs[0] if costs else 0.001),
        _resp(scores, cost=costs[1] if len(costs) > 1 else 0.001),
        _resp("done", cost=costs[2] if len(costs) > 2 else 0.001),
    ]


def _multi_agent_responses(costs: list[float]) -> list[LLMResponse]:
    plan = '{"assignments": [{"worker": "w", "task": "t"}]}'
    return [
        _resp(plan, cost=costs[0] if costs else 0.001),
        _resp("worker thought", cost=costs[1] if len(costs) > 1 else 0.001),
        _resp("aggregated", cost=costs[2] if len(costs) > 2 else 0.001),
    ]


def _assert_invariant(budget: BudgetPolicy, raised: bool, max_call_cost: float) -> None:
    """Either the run completed cleanly, or `BudgetExceeded` /
    `GuardrailViolation` raised. In both cases `spent_usd` cannot
    exceed the cap by more than ONE in-flight call's cost — the
    policy's `check()` runs *before* a call but `commit()` runs
    *after*, so a single call may push spend over the cap; subsequent
    calls are then blocked.
    """
    assert budget.spent_usd >= 0
    assert budget.spent_usd <= budget.usd + max_call_cost + 1e-9
    if raised:
        # The strategy stopped — must have actually hit some cap.
        # Either USD or iteration cap was reached.
        usd_capped = budget.spent_usd + 1e-9 >= budget.usd
        iter_capped = budget.iteration >= budget.max_iterations
        assert usd_capped or iter_capped


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    cap=st.floats(min_value=0.001, max_value=0.5),
    costs=st.lists(st.floats(min_value=0.0, max_value=0.2), min_size=3, max_size=10),
)
@pytest.mark.asyncio
async def test_react_budget_invariant(cap: float, costs: list[float]) -> None:
    fake = FakeLLMClient(responses=_react_responses(costs))
    state, _ = _make_state(fake, budget=BudgetPolicy(usd=cap, max_iterations=10))
    raised = False
    try:
        await ReActLoop(max_iterations=5).run(state)
    except (BudgetExceeded, GuardrailViolation):
        raised = True
    _assert_invariant(state.metadata[RUNTIME_KEY].budget, raised, max(costs, default=0.0))


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    cap=st.floats(min_value=0.001, max_value=0.5),
    costs=st.lists(st.floats(min_value=0.0, max_value=0.2), min_size=3, max_size=6),
)
@pytest.mark.asyncio
async def test_plan_execute_budget_invariant(cap: float, costs: list[float]) -> None:
    fake = FakeLLMClient(responses=_plan_responses(costs))
    state, _ = _make_state(fake, budget=BudgetPolicy(usd=cap, max_iterations=10))
    raised = False
    try:
        await PlanExecuteLoop(max_replans=0).run(state)
    except (BudgetExceeded, GuardrailViolation):
        raised = True
    _assert_invariant(state.metadata[RUNTIME_KEY].budget, raised, max(costs, default=0.0))


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    cap=st.floats(min_value=0.001, max_value=0.5),
    costs=st.lists(st.floats(min_value=0.0, max_value=0.2), min_size=3, max_size=6),
)
@pytest.mark.asyncio
async def test_tot_budget_invariant(cap: float, costs: list[float]) -> None:
    fake = FakeLLMClient(responses=_tot_responses(costs))
    state, _ = _make_state(fake, budget=BudgetPolicy(usd=cap, max_iterations=10))
    raised = False
    try:
        await TreeOfThoughts(branch_factor=1, depth=1).run(state)
    except (BudgetExceeded, GuardrailViolation):
        raised = True
    _assert_invariant(state.metadata[RUNTIME_KEY].budget, raised, max(costs, default=0.0))


class _NoopWorker:
    """A worker that does nothing (no LLM call). For property tests."""

    async def run(self, state: AgentState) -> AgentState:
        return state


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    cap=st.floats(min_value=0.001, max_value=0.5),
    costs=st.lists(st.floats(min_value=0.0, max_value=0.2), min_size=3, max_size=6),
)
@pytest.mark.asyncio
async def test_multi_agent_budget_invariant(cap: float, costs: list[float]) -> None:
    fake = FakeLLMClient(responses=_multi_agent_responses(costs))
    state, _ = _make_state(fake, budget=BudgetPolicy(usd=cap, max_iterations=10))
    raised = False
    try:
        await MultiAgentSupervisor(workers={"w": _NoopWorker()}).run(state)  # type: ignore[arg-type]
    except (BudgetExceeded, GuardrailViolation):
        raised = True
    _assert_invariant(state.metadata[RUNTIME_KEY].budget, raised, max(costs, default=0.0))
