"""Integration test — Agent + TreeOfThoughts end-to-end."""

from __future__ import annotations

import pytest
from agentforge import Agent, TreeOfThoughts
from agentforge._testing import FakeLLMClient
from agentforge_core.values.messages import LLMResponse, TokenUsage


def _r(content: str = "") -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=5, output_tokens=3),
        cost_usd=0.001,
        model="fake",
        provider="fake",
    )


@pytest.mark.asyncio
async def test_string_strategy_tot_runs_full_search() -> None:
    """Default ToT (branch_factor=3, depth=2, score_threshold=0.5):
    level 1 generate + score + level 2 generate + score + synthesize."""
    fake = FakeLLMClient(
        responses=[
            # Level 1
            _r(
                '{"thoughts": ['
                '{"id": "a", "content": "approach A"}, '
                '{"id": "b", "content": "approach B"}, '
                '{"id": "c", "content": "approach C"}'
                "]}"
            ),
            _r(
                '{"scores": ['
                '{"branch_id": "a", "score": 0.9, "reasoning": "x"}, '
                '{"branch_id": "b", "score": 0.4, "reasoning": "y"}, '
                '{"branch_id": "c", "score": 0.7, "reasoning": "z"}'
                "]}"
            ),
            # Level 2 (only "a" and "c" survive 0.5 threshold; both expand
            # in the same level-2 phase)
            _r(
                '{"thoughts": ['
                '{"id": "a1", "content": "refine A"}, '
                '{"id": "a2", "content": "alt A"}, '
                '{"id": "a3", "content": "third A"}'
                "]}"
            ),
            _r(
                '{"scores": ['
                '{"branch_id": "a1", "score": 0.95, "reasoning": ""}, '
                '{"branch_id": "a2", "score": 0.6, "reasoning": ""}, '
                '{"branch_id": "a3", "score": 0.3, "reasoning": ""}'
                "]}"
            ),
            _r(
                '{"thoughts": ['
                '{"id": "c1", "content": "refine C"}, '
                '{"id": "c2", "content": "alt C"}, '
                '{"id": "c3", "content": "third C"}'
                "]}"
            ),
            _r(
                '{"scores": ['
                '{"branch_id": "c1", "score": 0.55, "reasoning": ""}, '
                '{"branch_id": "c2", "score": 0.4, "reasoning": ""}, '
                '{"branch_id": "c3", "score": 0.5, "reasoning": ""}'
                "]}"
            ),
            _r("Final answer using best path."),
        ]
    )
    async with Agent(
        model=fake,
        strategy="tot",
        budget_usd=5.0,
        install_log_filter=False,
    ) as agent:
        result = await agent.run("Solve this problem.")

    assert result.output == "Final answer using best path."
    assert result.finish_reason == "completed"
    kinds = {s.kind for s in result.steps}
    assert "branch" in kinds
    assert "synthesize" in kinds


@pytest.mark.asyncio
async def test_typed_tot_instance() -> None:
    fake = FakeLLMClient(
        responses=[
            _r('{"thoughts": [{"id": "a", "content": "x"}]}'),
            _r('{"scores": [{"branch_id": "a", "score": 0.9, "reasoning": ""}]}'),
            _r("done"),
        ]
    )
    async with Agent(
        model=fake,
        strategy=TreeOfThoughts(branch_factor=1, depth=1, score_threshold=0.5),
        install_log_filter=False,
    ) as agent:
        result = await agent.run("test")
    assert result.output == "done"
