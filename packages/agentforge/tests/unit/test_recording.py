"""Tests for feat-017 run-recording protocol."""

from __future__ import annotations

import pytest
from agentforge import Agent, InMemoryStore
from agentforge.recording import (
    RUN_CATEGORY,
    STEP_CATEGORY,
    RecordRunHook,
)
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.claim import Claim
from agentforge_core.values.state import AgentState, Step


class _TwoStepStrategy(ReasoningStrategy):
    """Emits two steps (think + observe) so recording has something to do."""

    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="think", content="reasoning"))
        state.steps.append(Step(iteration=1, kind="observe", content="final answer"))
        return state


@pytest.mark.asyncio
async def test_record_run_hook_persists_each_step_as_claim() -> None:
    memory = InMemoryStore()
    agent = Agent(strategy=_TwoStepStrategy(), record_runs=memory)
    result = await agent.run("hello")

    step_claims = await memory.query(category=STEP_CATEGORY)
    assert len(step_claims) == 2, "one claim per emitted Step"
    kinds = [c.payload["kind"] for c in step_claims]
    assert kinds == ["think", "observe"]
    assert all(c.run_id == result.run_id for c in step_claims)


@pytest.mark.asyncio
async def test_record_run_hook_writes_run_summary_claim() -> None:
    memory = InMemoryStore()
    agent = Agent(strategy=_TwoStepStrategy(), record_runs=memory)
    result = await agent.run("hello")

    run_claims = await memory.query(category=RUN_CATEGORY, run_id=result.run_id)
    assert len(run_claims) == 1
    payload = run_claims[0].payload
    assert payload["finish_reason"] == "completed"
    assert payload["cost_usd"] == pytest.approx(0.0)
    assert "tokens_in" in payload
    assert "duration_ms" in payload


@pytest.mark.asyncio
async def test_record_run_hook_can_be_invoked_directly() -> None:
    """The hook works outside Agent.run() — useful for tests + replay."""
    memory = InMemoryStore()
    hook = RecordRunHook(memory=memory, project="test", agent_name="bot")
    await hook.on_step(Step(iteration=0, kind="think", content="x"))
    rows = await memory.query(category=STEP_CATEGORY)
    assert len(rows) == 1
    # No active RunContext; falls back to the sentinel run_id.
    assert rows[0].run_id == "unknown"


@pytest.mark.asyncio
async def test_record_run_hook_serializes_step_metadata() -> None:
    memory = InMemoryStore()
    hook = RecordRunHook(memory=memory, project="p", agent_name="a")
    step = Step(
        iteration=3,
        kind="act",
        content={"reason": "calling tool"},
        tokens_in=12,
        tokens_out=4,
        cost_usd=0.001,
        metadata={"trace_id": "abc"},
    )
    await hook.on_step(step)
    [claim] = await memory.query(category=STEP_CATEGORY)
    assert claim.payload["iteration"] == 3
    assert claim.payload["kind"] == "act"
    assert claim.payload["content"] == {"reason": "calling tool"}
    assert claim.payload["tokens_in"] == 12
    assert claim.payload["metadata"] == {"trace_id": "abc"}


@pytest.mark.asyncio
async def test_in_memory_delete_refuses_total_wipe() -> None:
    memory = InMemoryStore()
    with pytest.raises(ModuleError, match="at least one filter"):
        await memory.delete()


@pytest.mark.asyncio
async def test_in_memory_delete_by_run_id_returns_count() -> None:
    memory = InMemoryStore()
    await memory.put(Claim(run_id="r1", project="p", agent="a", category="c", payload={}))
    await memory.put(Claim(run_id="r1", project="p", agent="a", category="c", payload={}))
    await memory.put(Claim(run_id="r2", project="p", agent="a", category="c", payload={}))

    removed = await memory.delete(run_id="r1")
    assert removed == 2
    remaining = await memory.query()
    assert all(c.run_id == "r2" for c in remaining)
