"""Unit tests for the `Task` ABC (feat-015)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.task import Task


@dataclass
class _MiniFinding:
    severity: str
    category: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
        }


def test_task_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError, match="abstract"):
        Task()  # type: ignore[abstract]


def test_concrete_task_without_name_raises_at_definition() -> None:
    with pytest.raises(TypeError, match="must declare class attribute 'name'"):

        class _BadTask(Task):
            async def run(self, context: Mapping[str, Any]) -> list[Finding]:
                return []


@pytest.mark.asyncio
async def test_minimal_subclass_runs_and_returns_findings() -> None:
    class CoverageTask(Task):
        name = "coverage"
        cost_estimate_usd = 0.0
        timeout_s = 30.0
        depends_on = ()

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            return [_MiniFinding(severity="info", category="coverage", message="ok")]

    t = CoverageTask()
    out = await t.run({})
    assert len(out) == 1
    assert out[0].category == "coverage"


def test_depends_on_is_inheritable() -> None:
    class _A(Task):
        name = "a"

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            return []

    class _B(_A):
        # subclass redeclares only 'name' (other ClassVars inherit defaults)
        name = "b"

    assert _B.depends_on == ()
    assert _B.cost_estimate_usd == 0.0
    assert _B.timeout_s == 60.0
