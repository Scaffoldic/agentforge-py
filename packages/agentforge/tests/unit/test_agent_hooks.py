"""Unit tests for `Agent`'s on_step / on_finish hook plumbing (feat-009 chunk 1).

Verifies:
  - `on_step` actually fires for every step appended (was a gap until
    feat-009 — feat-001 accepted the kwarg but never fired it).
  - `on_step` and `on_finish` accept a single callable OR a list.
  - Sync hooks run inline; async hooks are awaited.
  - A raising hook is isolated — logs WARN via `agentforge.observability`
    and the run keeps going. Other hooks still fire.
  - Hook ordering is preserved.
  - `on_step` also fires on error paths (strategy raised) so partial
    traces stay observable.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from agentforge import Agent
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.production.exceptions import AgentForgeError
from agentforge_core.values.state import AgentState, Step


class _StrategyEmittingThree(ReasoningStrategy):
    """Test strategy: appends three steps then returns."""

    async def run(self, state: AgentState) -> AgentState:
        for i in range(3):
            state.steps.append(Step(iteration=i, kind="observe", content=f"step-{i}"))
        return state


class _StrategyRaising(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="observe", content="before-raise"))
        raise AgentForgeError("kaboom")


# --- on_step actually fires ------------------------------------------


@pytest.mark.asyncio
async def test_on_step_fires_for_every_step() -> None:
    seen: list[Step] = []

    def record(step: Step) -> None:
        seen.append(step)

    async with Agent(strategy=_StrategyEmittingThree(), on_step=record) as agent:
        await agent.run("hello")

    assert [s.content for s in seen] == ["step-0", "step-1", "step-2"]


# --- list-of-hooks fan-out ------------------------------------------


@pytest.mark.asyncio
async def test_on_step_accepts_list_of_hooks() -> None:
    seen_a: list[str] = []
    seen_b: list[str] = []

    def hook_a(step: Step) -> None:
        seen_a.append(str(step.content))

    def hook_b(step: Step) -> None:
        seen_b.append(str(step.content))

    async with Agent(strategy=_StrategyEmittingThree(), on_step=[hook_a, hook_b]) as agent:
        await agent.run("hello")

    assert seen_a == ["step-0", "step-1", "step-2"]
    assert seen_b == ["step-0", "step-1", "step-2"]


@pytest.mark.asyncio
async def test_on_finish_accepts_list_of_hooks() -> None:
    seen: list[str] = []

    def hook_a(result: Any) -> None:
        seen.append(f"a:{result.run_id}")

    def hook_b(result: Any) -> None:
        seen.append(f"b:{result.run_id}")

    async with Agent(strategy=_StrategyEmittingThree(), on_finish=[hook_a, hook_b]) as agent:
        result = await agent.run("hello")

    assert seen == [f"a:{result.run_id}", f"b:{result.run_id}"]


# --- async hooks ----------------------------------------------------


@pytest.mark.asyncio
async def test_async_hook_is_awaited() -> None:
    seen: list[Step] = []

    async def async_hook(step: Step) -> None:
        seen.append(step)

    async with Agent(strategy=_StrategyEmittingThree(), on_step=async_hook) as agent:
        await agent.run("hello")

    assert len(seen) == 3


# --- error isolation -----------------------------------------------


@pytest.mark.asyncio
async def test_raising_hook_does_not_crash_run(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="agentforge.observability")
    seen: list[Step] = []

    def bad_hook(step: Step) -> None:
        raise RuntimeError("hook is broken")

    def good_hook(step: Step) -> None:
        seen.append(step)

    async with Agent(strategy=_StrategyEmittingThree(), on_step=[bad_hook, good_hook]) as agent:
        result = await agent.run("hello")

    # Run completed normally; good hook fired for every step.
    assert result.finish_reason == "completed"
    assert len(seen) == 3
    # WARN logged for each failed invocation (3 steps * 1 bad hook).
    assert sum(1 for r in caplog.records if "hook on_step raised RuntimeError" in r.message) == 3


@pytest.mark.asyncio
async def test_raising_finish_hook_does_not_propagate(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="agentforge.observability")
    seen: list[Any] = []

    def bad_hook(result: Any) -> None:
        raise RuntimeError("finish hook broken")

    def good_hook(result: Any) -> None:
        seen.append(result)

    async with Agent(strategy=_StrategyEmittingThree(), on_finish=[bad_hook, good_hook]) as agent:
        result = await agent.run("hello")

    assert result.finish_reason == "completed"
    assert len(seen) == 1
    assert any("hook on_finish raised RuntimeError" in r.message for r in caplog.records)


# --- error path: on_step still fires when strategy raises -----------


@pytest.mark.asyncio
async def test_on_step_fires_on_error_path() -> None:
    seen: list[Step] = []

    def hook(step: Step) -> None:
        seen.append(step)

    async with Agent(strategy=_StrategyRaising(), on_step=hook) as agent:
        with pytest.raises(AgentForgeError):
            await agent.run("hello")

    # The strategy appended one step before raising; the hook saw it.
    assert len(seen) == 1
    assert seen[0].content == "before-raise"


# --- ordering -------------------------------------------------------


@pytest.mark.asyncio
async def test_hook_invocation_order() -> None:
    """For each step, hooks fire in registration order; then the next
    step's hooks fire."""
    order: list[str] = []

    def hook_a(step: Step) -> None:
        order.append(f"a-{step.content}")

    def hook_b(step: Step) -> None:
        order.append(f"b-{step.content}")

    async with Agent(strategy=_StrategyEmittingThree(), on_step=[hook_a, hook_b]) as agent:
        await agent.run("hello")

    assert order == [
        "a-step-0",
        "b-step-0",
        "a-step-1",
        "b-step-1",
        "a-step-2",
        "b-step-2",
    ]
