"""Conformance harness exercises for `Task` (feat-015)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.task import Task
from agentforge_core.testing import run_task_conformance


@dataclass
class _MiniFinding:
    severity: str
    category: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "category": self.category, "message": self.message}


class _GoodTask(Task):
    name = "good"
    cost_estimate_usd = 0.0
    timeout_s = 10.0
    depends_on = ()

    async def run(self, context: Mapping[str, Any]) -> list[Finding]:
        return [_MiniFinding(severity="info", category="ok", message="hello")]


@pytest.mark.asyncio
async def test_run_task_conformance_passes_on_good_task() -> None:
    await run_task_conformance(_GoodTask())


@pytest.mark.asyncio
async def test_run_task_conformance_rejects_non_list_return() -> None:
    class _BadReturn(Task):
        name = "bad-return"

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            return "nope"  # type: ignore[return-value]

    with pytest.raises(AssertionError, match="must return a list"):
        await run_task_conformance(_BadReturn())


@pytest.mark.asyncio
async def test_run_task_conformance_rejects_empty_name() -> None:
    class _Empty(Task):
        name = ""

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            return []

    with pytest.raises(AssertionError, match="must be non-empty"):
        await run_task_conformance(_Empty())


@pytest.mark.asyncio
async def test_run_task_conformance_rejects_negative_cost() -> None:
    class _NegCost(Task):
        name = "neg"
        cost_estimate_usd = -1.0

        async def run(self, context: Mapping[str, Any]) -> list[Finding]:
            return []

    with pytest.raises(AssertionError, match="non-negative"):
        await run_task_conformance(_NegCost())
