"""Unit tests for `TreeOfThoughts.stream()` (feat-002 v0.3 polish).

Exercises the per-depth streaming override: yields ``branch`` step
events for each generated thought (as they're recorded inside
``_iterate_depth``), the final ``synthesize`` step, and the
terminal ``done`` event.
"""

from __future__ import annotations

import pytest
from agentforge import Agent
from agentforge._testing import FakeLLMClient
from agentforge.strategies.tot import TreeOfThoughts
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


def _thoughts(n: int) -> str:
    items = [f'{{"id": "t{i}", "content": "thought {i}"}}' for i in range(1, n + 1)]
    return '{"thoughts": [' + ", ".join(items) + "]}"


def _scores(scores_by_id: dict[str, float]) -> str:
    items = [
        f'{{"branch_id": "{k}", "score": {v}, "reasoning": "..."}}' for k, v in scores_by_id.items()
    ]
    return '{"scores": [' + ", ".join(items) + "]}"


@pytest.mark.asyncio
async def test_stream_emits_branch_synthesize_then_canonical_done() -> None:
    """depth=1, branch_factor=2: two `branch` steps + one
    `synthesize` step + canonical done.
    """
    fake = FakeLLMClient(
        responses=[
            _resp(_thoughts(2)),
            _resp(_scores({"t1": 0.9, "t2": 0.6})),
            _resp("final answer based on best branch"),
        ]
    )
    agent = Agent(
        model=fake,
        tools=[],
        strategy=TreeOfThoughts(branch_factor=2, depth=1, score_threshold=0.5),
    )

    events = [event async for event in agent.stream("solve x")]
    kinds = [e.kind for e in events]

    assert kinds[-1] == "done"
    assert all(k == "step" for k in kinds[:-1])

    step_metadata_kinds = [e.metadata["kind"] for e in events if e.kind == "step"]
    assert step_metadata_kinds.count("branch") == 2
    assert step_metadata_kinds[-1] == "synthesize"

    # Canonical done from Agent.stream carries the RunResult shape.
    done = events[-1]
    assert isinstance(done.content, dict)
    assert "run_id" in done.content
    assert "output" in done.content


@pytest.mark.asyncio
async def test_strategy_stream_yields_strategy_level_done_when_driven_directly() -> None:
    """Direct `strategy.stream(state)` surfaces the strategy-level
    done (just run_id + cost_usd)."""
    from agentforge import InMemoryStore  # noqa: PLC0415
    from agentforge.runtime import RUNTIME_KEY, RuntimeContext  # noqa: PLC0415
    from agentforge_core.production.budget import BudgetPolicy  # noqa: PLC0415
    from agentforge_core.values.state import AgentState  # noqa: PLC0415

    fake = FakeLLMClient(
        responses=[
            _resp(_thoughts(1)),
            _resp(_scores({"t1": 0.9})),
            _resp("final"),
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

    events = [
        event
        async for event in TreeOfThoughts(branch_factor=1, depth=1, score_threshold=0.5).stream(
            state
        )
    ]

    assert events[-1].kind == "done"
    assert isinstance(events[-1].content, dict)
    assert set(events[-1].content.keys()) == {"run_id", "cost_usd"}
