"""Unit tests for `PlanExecuteLoop.stream()` (feat-002 v0.3 polish).

Exercises the per-phase streaming override: emit a ``plan`` step
event, then one ``observe`` per execute step, then a ``synthesize``
step, then the canonical ``done``.
"""

from __future__ import annotations

import pytest
from agentforge import Agent
from agentforge._testing import FakeLLMClient
from agentforge.strategies.plan_execute import PlanExecuteLoop
from agentforge_core.values.messages import LLMResponse, TokenUsage


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
async def test_stream_emits_plan_observe_synthesize_then_canonical_done() -> None:
    """Two think-only steps + synthesize: stream events in order.

    Plan: two think-only steps (no dependencies → execute in parallel).
    Expected sequence under `Agent.stream(task)`:
      step (plan) → step (think) → step (think) → step (observe) →
      step (observe) → step (synthesize) → done
    """
    plan_json = (
        '{"steps": ['
        '{"id": "s1", "description": "think about A", "tool": null, '
        '"arguments": {}, "depends_on": []},'
        '{"id": "s2", "description": "think about B", "tool": null, '
        '"arguments": {}, "depends_on": []}'
        "]}"
    )
    fake = FakeLLMClient(
        responses=[
            _resp(plan_json),
            # Two think-only step LLM calls (parallel batch, order may vary):
            _resp("about A"),
            _resp("about B"),
            # Synthesis:
            _resp("final answer combining A and B"),
        ]
    )
    agent = Agent(model=fake, tools=[], strategy=PlanExecuteLoop(max_parallel_steps=2))

    events = [event async for event in agent.stream("combine A and B")]
    kinds = [e.kind for e in events]

    # All events except the final agent-canonical done are step events.
    assert kinds[-1] == "done"
    assert all(k == "step" for k in kinds[:-1])

    step_metadata_kinds = [e.metadata["kind"] for e in events if e.kind == "step"]
    # `_call_llm(kind="think")` inside `_build_plan` records a `think`
    # step first, then the explicit `plan` step is recorded — both
    # land before the execute phase starts.
    assert step_metadata_kinds[0] == "think"
    assert step_metadata_kinds[1] == "plan"
    # Synthesize step is last.
    assert step_metadata_kinds[-1] == "synthesize"
    # Between plan and synthesize: two `act` (think-only steps record
    # an `act` via `_call_llm(kind="act")`) and two `observe` records.
    middle = step_metadata_kinds[2:-1]
    assert middle.count("act") == 2
    assert middle.count("observe") == 2

    # Final done carries the agent-canonical RunResult shape.
    done = events[-1]
    assert isinstance(done.content, dict)
    assert "run_id" in done.content
    assert "output" in done.content


@pytest.mark.asyncio
async def test_strategy_stream_yields_strategy_level_done_when_driven_directly() -> None:
    """Direct `strategy.stream(state)` surfaces the strategy-level
    done (just run_id + cost_usd, not the full RunResult)."""
    from agentforge import InMemoryStore  # noqa: PLC0415
    from agentforge.runtime import RUNTIME_KEY, RuntimeContext  # noqa: PLC0415
    from agentforge_core.production.budget import BudgetPolicy  # noqa: PLC0415
    from agentforge_core.values.state import AgentState  # noqa: PLC0415

    plan_json = (
        '{"steps": ['
        '{"id": "s1", "description": "think about it", "tool": null, '
        '"arguments": {}, "depends_on": []}'
        "]}"
    )
    fake = FakeLLMClient(
        responses=[
            _resp(plan_json),
            _resp("thought"),
            _resp("synth"),
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
                budget=BudgetPolicy(usd=2.0, max_iterations=10),
            ),
        },
    )

    events = [event async for event in PlanExecuteLoop().stream(state)]

    assert events[-1].kind == "done"
    assert isinstance(events[-1].content, dict)
    assert set(events[-1].content.keys()) == {"run_id", "cost_usd"}
