"""Integration test — Agent + MultiAgentSupervisor end-to-end."""

from __future__ import annotations

import pytest
from agentforge import Agent, MultiAgentSupervisor, ReActLoop
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
async def test_string_strategy_multi_agent_runs_end_to_end() -> None:
    """Default-ish multi-agent: 1 supervisor delegate + 2 workers + 1 aggregate."""
    fake = FakeLLMClient(
        responses=[
            # Supervisor delegation plan
            _r(
                '{"assignments": ['
                '{"worker": "researcher", "task": "find facts"}, '
                '{"worker": "writer", "task": "summarise"}'
                "]}"
            ),
            # researcher (ReActLoop) — one think, terminates
            _r("researcher thinks and finishes"),
            # writer (ReActLoop) — one think, terminates
            _r("writer thinks and finishes"),
            # supervisor aggregation
            _r("Final answer combining both."),
        ]
    )
    async with Agent(
        model=fake,
        strategy=MultiAgentSupervisor(
            workers={
                "researcher": ReActLoop(max_iterations=3),
                "writer": ReActLoop(max_iterations=3),
            }
        ),
        budget_usd=5.0,
        install_log_filter=False,
    ) as agent:
        result = await agent.run("Investigate and summarise topic X.")

    assert result.output == "Final answer combining both."
    assert result.finish_reason == "completed"
    kinds = {s.kind for s in result.steps}
    assert "delegate" in kinds
    assert "synthesize" in kinds


@pytest.mark.asyncio
async def test_typed_multi_agent_instance_with_descriptions() -> None:
    fake = FakeLLMClient(
        responses=[
            _r('{"assignments": [{"worker": "solo", "task": "do it"}]}'),
            _r("solo finished"),
            _r("aggregated."),
        ]
    )
    async with Agent(
        model=fake,
        strategy=MultiAgentSupervisor(
            workers={"solo": ReActLoop(max_iterations=2)},
            worker_descriptions={"solo": "lone specialist"},
        ),
        install_log_filter=False,
    ) as agent:
        result = await agent.run("test")
    assert result.output == "aggregated."
