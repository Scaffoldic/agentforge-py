"""Agent + Pipeline integration tests (feat-015)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from agentforge.agent import Agent
from agentforge.findings import SimpleFinding
from agentforge.memory import InMemoryStore
from agentforge.pipeline import Pipeline, PipelineFailure, PipelineFindingsTool
from agentforge.recording import PIPELINE_CATEGORY
from agentforge.replay import load_pipeline_result
from agentforge.runtime import RUNTIME_KEY
from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.contracts.task import Task
from agentforge_core.production.exceptions import BudgetExceeded
from agentforge_core.values.messages import LLMResponse, Message, TokenUsage, ToolSpec
from agentforge_core.values.state import AgentState, Step

# ----------------------------------------------------------------------
# Test fixtures: stub strategy + stub LLM.
# ----------------------------------------------------------------------


class _CapturingStrategy(ReasoningStrategy):
    """ReasoningStrategy stub: records the system prompt + tools it sees."""

    def __init__(self) -> None:
        self.captured_system_prompt: str | None = None
        self.captured_tool_names: tuple[str, ...] = ()
        self.last_pipeline_findings: list[dict[str, Any]] = []

    async def run(self, state: AgentState) -> AgentState:
        runtime = state.metadata[RUNTIME_KEY]
        self.captured_system_prompt = runtime.system_prompt
        self.captured_tool_names = tuple(type(t).name for t in runtime.tools)
        # Invoke the pipeline_findings tool if present, to validate it
        # returns the cached findings.
        for tool in runtime.tools:
            if type(tool).name == "pipeline_findings":
                self.last_pipeline_findings = await tool.run()
        state.steps.append(Step(iteration=0, kind="system", content="ok"))
        return state


class _FakeLLM(LLMClient):
    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        del system, messages, tools
        return LLMResponse(
            content="",
            tool_calls=(),
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=0, output_tokens=0),
            cost_usd=0.0,
            model="fake",
            provider="fake",
        )

    async def close(self) -> None:
        return None


class _LintTask(Task):
    name = "lint"

    async def run(self, context: Mapping[str, Any]) -> list[Finding]:
        return [SimpleFinding(severity="warning", category="lint", message="trailing space")]


class _CoverageTask(Task):
    name = "coverage"
    cost_estimate_usd = 0.0

    async def run(self, context: Mapping[str, Any]) -> list[Finding]:
        return [SimpleFinding(severity="info", category="coverage", message="92% covered")]


def _agent_with(strategy: Any, **kwargs: Any) -> Agent:
    return Agent(
        model=_FakeLLM(),
        strategy=strategy,
        system_prompt="You are a reviewer.",
        memory=InMemoryStore(),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_agent_runs_pipeline_before_strategy() -> None:
    strategy = _CapturingStrategy()
    pipeline = Pipeline([_LintTask(), _CoverageTask()])
    agent = _agent_with(strategy, pipeline=pipeline)
    await agent.run("review this PR", context={"repo_path": "./repo"})
    assert "pipeline_findings" in strategy.captured_tool_names
    # System-prompt addendum is appended.
    assert strategy.captured_system_prompt is not None
    assert "Pipeline findings" in strategy.captured_system_prompt
    # The pipeline_findings tool returns serialised findings.
    cats = {f["category"] for f in strategy.last_pipeline_findings}
    assert "lint" in cats
    assert "coverage" in cats


@pytest.mark.asyncio
async def test_no_pipeline_means_no_addendum_or_tool() -> None:
    strategy = _CapturingStrategy()
    agent = _agent_with(strategy)
    await agent.run("hello")
    assert "pipeline_findings" not in strategy.captured_tool_names
    assert strategy.captured_system_prompt == "You are a reviewer."


@pytest.mark.asyncio
async def test_pipeline_fail_mode_sets_finish_reason_pipeline() -> None:
    class _Boom(Task):
        name = "boom"

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            raise RuntimeError("kaboom")

    pipeline = Pipeline([_Boom()], on_task_error="fail")
    agent = _agent_with(_CapturingStrategy(), pipeline=pipeline)
    with pytest.raises(PipelineFailure):
        await agent.run("anything")


@pytest.mark.asyncio
async def test_pipeline_over_budget_raises_budget_exceeded() -> None:
    class _Expensive(Task):
        name = "expensive"
        cost_estimate_usd = 5.0

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            return []

    agent = _agent_with(_CapturingStrategy(), pipeline=Pipeline([_Expensive()]), budget_usd=1.0)
    with pytest.raises(BudgetExceeded):
        await agent.run("anything")


@pytest.mark.asyncio
async def test_replay_pipeline_skips_execution() -> None:
    counter = {"runs": 0}

    class _CountingLint(Task):
        name = "counting-lint"

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            counter["runs"] += 1
            return [SimpleFinding(severity="info", category="lint", message="ok")]

    pipeline = Pipeline([_CountingLint()])
    strategy = _CapturingStrategy()
    memory = InMemoryStore()
    agent = _agent_with(strategy, pipeline=pipeline, record_runs=memory)
    result_a = await agent.run("first")
    assert counter["runs"] == 1
    # Now replay: build a fresh agent with the same pipeline but
    # pass the recorded PipelineResult so it doesn't re-run.
    recorded = await load_pipeline_result(memory, result_a.run_id)
    assert recorded is not None
    strategy_b = _CapturingStrategy()
    agent_b = _agent_with(strategy_b, pipeline=pipeline)
    await agent_b.run("first", replay_pipeline=recorded)
    assert counter["runs"] == 1  # NOT re-executed
    cats = {f["category"] for f in strategy_b.last_pipeline_findings}
    assert "lint" in cats


@pytest.mark.asyncio
async def test_recording_writes_pipeline_claim() -> None:
    pipeline = Pipeline([_LintTask()])
    memory = InMemoryStore()
    agent = _agent_with(_CapturingStrategy(), pipeline=pipeline, record_runs=memory)
    result = await agent.run("review")
    claims = await memory.query(category=PIPELINE_CATEGORY, run_id=result.run_id)
    assert len(claims) == 1
    findings = claims[0].payload["findings"]
    assert any(f["category"] == "lint" for f in findings)


@pytest.mark.asyncio
async def test_pipeline_findings_tool_filters_by_category() -> None:
    tool = PipelineFindingsTool()
    tool._set_cache(
        [
            SimpleFinding(severity="info", category="lint", message="a"),
            SimpleFinding(severity="warning", category="security", message="b"),
        ]
    )
    only_lint = await tool.run(category="lint")
    assert len(only_lint) == 1
    assert only_lint[0]["category"] == "lint"


@pytest.mark.asyncio
async def test_pipeline_findings_tool_filters_by_severity() -> None:
    tool = PipelineFindingsTool()
    tool._set_cache(
        [
            SimpleFinding(severity="info", category="lint", message="a"),
            SimpleFinding(severity="warning", category="security", message="b"),
        ]
    )
    only_warn = await tool.run(severity="warning")
    assert len(only_warn) == 1
    assert only_warn[0]["severity"] == "warning"
