"""Unit tests for `MultiAgentSupervisor.stream()` (feat-002 v0.3 polish).

Exercises the per-round streaming override: yields a ``plan`` step
event after the supervisor's delegation LLM call, a ``delegate``
step per worker output, the final ``synthesize`` aggregate step,
and the terminal ``done`` event.
"""

from __future__ import annotations

import pytest
from agentforge import Agent, InMemoryStore
from agentforge._testing import FakeLLMClient
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge.strategies import MultiAgentSupervisor
from agentforge.strategies._base import get_runtime
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.values.messages import LLMResponse, TokenUsage
from agentforge_core.values.state import AgentState, Step


class _ScriptedWorker(ReasoningStrategy):
    """Worker that appends a synthesize step with a fixed reply."""

    def __init__(self, reply: str = "worker output") -> None:
        self.reply = reply

    async def run(self, state):
        rt = get_runtime(state)
        rt.budget.check()
        state.steps.append(Step(iteration=1, kind="synthesize", content=self.reply, cost_usd=0.0))
        return state


def _resp(content: str, *, cost: float = 0.0) -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        cost_usd=cost,
        model="fake",
        provider="fake",
    )


@pytest.mark.asyncio
async def test_stream_emits_plan_delegate_synthesize_then_canonical_done() -> None:
    """One round, one worker, then aggregate. Expected step sequence:

    - ``plan`` (delegation plan LLM call) → recorded by `_delegate`
    - ``delegate`` (one per worker output) → recorded by `_execute_workers`
    - ``synthesize`` (aggregate LLM call) → recorded by `_aggregate`
    - canonical ``done`` emitted by `Agent.stream`
    """
    fake = FakeLLMClient(
        responses=[
            _resp('{"assignments": [{"worker": "a", "task": "subtask 1"}]}'),
            _resp("aggregated final answer"),
        ]
    )
    agent = Agent(
        model=fake,
        tools=[],
        strategy=MultiAgentSupervisor(workers={"a": _ScriptedWorker()}, max_rounds=1),
    )

    events = [event async for event in agent.stream("big task")]
    kinds = [e.kind for e in events]

    assert kinds[-1] == "done"
    assert all(k == "step" for k in kinds[:-1])

    step_metadata_kinds = [e.metadata["kind"] for e in events if e.kind == "step"]
    assert step_metadata_kinds[0] == "plan"
    assert step_metadata_kinds.count("delegate") == 1
    assert step_metadata_kinds[-1] == "synthesize"

    done = events[-1]
    assert isinstance(done.content, dict)
    assert "run_id" in done.content
    assert "output" in done.content


@pytest.mark.asyncio
async def test_strategy_stream_yields_strategy_level_done_when_driven_directly() -> None:
    """Direct `strategy.stream(state)` surfaces the strategy-level
    done (just run_id + cost_usd)."""
    fake = FakeLLMClient(
        responses=[
            _resp('{"assignments": [{"worker": "a", "task": "subtask 1"}]}'),
            _resp("aggregated"),
        ]
    )
    state = AgentState(
        run_id="r-1",
        task="t",
        metadata={
            RUNTIME_KEY: RuntimeContext(
                llm=fake,
                tools=(),
                memory=InMemoryStore(),
                budget=BudgetPolicy(usd=5.0, max_iterations=10),
            ),
        },
    )

    events = [
        event
        async for event in MultiAgentSupervisor(
            workers={"a": _ScriptedWorker()}, max_rounds=1
        ).stream(state)
    ]

    assert events[-1].kind == "done"
    assert isinstance(events[-1].content, dict)
    assert set(events[-1].content.keys()) == {"run_id", "cost_usd"}
