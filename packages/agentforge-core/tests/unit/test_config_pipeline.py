"""Unit tests for `PipelineConfig` / `PipelineTaskEntry` (feat-015)."""

from __future__ import annotations

import pytest
from agentforge_core.config.schema import (
    AgentForgeConfig,
    ModulesConfig,
    PipelineConfig,
    PipelineTaskEntry,
)
from pydantic import ValidationError


def test_pipeline_defaults() -> None:
    cfg = PipelineConfig()
    assert cfg.enabled is True
    assert cfg.max_concurrent == 4
    assert cfg.on_task_error == "continue"
    assert cfg.tasks == []


def test_pipeline_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        PipelineConfig(unknown_field=1)  # type: ignore[call-arg]


def test_pipeline_rejects_zero_max_concurrent() -> None:
    with pytest.raises(ValidationError):
        PipelineConfig(max_concurrent=0)


def test_pipeline_rejects_invalid_on_task_error() -> None:
    with pytest.raises(ValidationError):
        PipelineConfig(on_task_error="abort")  # type: ignore[arg-type]


def test_pipeline_task_entry_requires_name() -> None:
    with pytest.raises(ValidationError):
        PipelineTaskEntry(name="")


def test_modules_config_pipeline_defaults_to_none() -> None:
    cfg = ModulesConfig()
    assert cfg.pipeline is None


def test_full_config_round_trip() -> None:
    raw = {
        "modules": {
            "pipeline": {
                "max_concurrent": 8,
                "on_task_error": "fail",
                "tasks": [{"name": "lint", "config": {"strict": True}}],
            }
        }
    }
    cfg = AgentForgeConfig.model_validate(raw)
    assert cfg.modules.pipeline is not None
    assert cfg.modules.pipeline.max_concurrent == 8
    assert cfg.modules.pipeline.on_task_error == "fail"
    assert cfg.modules.pipeline.tasks[0].name == "lint"
    assert cfg.modules.pipeline.tasks[0].config == {"strict": True}
