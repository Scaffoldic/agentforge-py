"""Tests for `build_pipeline_from_config` (feat-015 chunk 4)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from agentforge.cli._build import build_agent_from_config, build_pipeline_from_config
from agentforge.findings import SimpleFinding
from agentforge.pipeline import Pipeline
from agentforge.resolver_register import register_task
from agentforge_core.config.schema import (
    AgentConfig,
    AgentForgeConfig,
    ModulesConfig,
    PipelineConfig,
    PipelineTaskEntry,
)
from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.task import Task


@register_task("_cli_build_dummy_lint")
class _DummyLint(Task):
    name = "_cli_build_dummy_lint"

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict

    async def run(self, context: Mapping[str, Any]) -> list[Finding]:
        sev = "error" if self.strict else "info"
        return [SimpleFinding(severity=sev, category="lint", message="ok")]


def test_build_pipeline_returns_none_when_absent() -> None:
    cfg = AgentForgeConfig()
    assert build_pipeline_from_config(cfg) is None


def test_build_pipeline_returns_none_when_disabled() -> None:
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            pipeline=PipelineConfig(
                enabled=False,
                tasks=[PipelineTaskEntry(name="_cli_build_dummy_lint")],
            )
        )
    )
    assert build_pipeline_from_config(cfg) is None


def test_build_pipeline_constructs_tasks_with_config() -> None:
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            pipeline=PipelineConfig(
                max_concurrent=2,
                on_task_error="fail",
                tasks=[PipelineTaskEntry(name="_cli_build_dummy_lint", config={"strict": True})],
            )
        )
    )
    pipeline = build_pipeline_from_config(cfg)
    assert isinstance(pipeline, Pipeline)
    assert pipeline.max_concurrent == 2
    assert pipeline.on_task_error == "fail"
    assert len(pipeline.tasks) == 1
    assert isinstance(pipeline.tasks[0], _DummyLint)
    assert pipeline.tasks[0].strict is True


@pytest.mark.asyncio
async def test_build_agent_wires_pipeline_and_tool() -> None:
    cfg = AgentForgeConfig(
        agent=AgentConfig(strategy="react"),
        modules=ModulesConfig(
            pipeline=PipelineConfig(
                tasks=[PipelineTaskEntry(name="_cli_build_dummy_lint")],
            )
        ),
    )
    agent = await build_agent_from_config(cfg)
    assert agent.pipeline is not None
    tool_names = {type(t).name for t in agent.tools}
    assert "pipeline_findings" in tool_names
