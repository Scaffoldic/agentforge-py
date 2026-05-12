"""`ReasoningStrategy.stream()` default-impl smoke tests (feat-020 v0.2)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.chat import StreamingEvent
from agentforge_core.values.state import AgentState, Step


class _NoopStrategy(ReasoningStrategy):
    """Doesn't override `stream()`; uses the default ABC impl."""

    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="think", content="ok"))
        return state


class _OverridingStrategy(ReasoningStrategy):
    """Real per-token override — emits three `text` events + a `done`."""

    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="think", content="ok"))
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[StreamingEvent]:
        cumulative = ""
        for piece in ("Hel", "lo, ", "world"):
            cumulative += piece
            yield StreamingEvent(kind="text", content=piece, cumulative_text=cumulative)
        yield StreamingEvent(
            kind="done",
            content={"run_id": state.run_id, "cost_usd": 0.0},
        )


@pytest.mark.asyncio
async def test_default_stream_yields_one_done_event() -> None:
    strategy = _NoopStrategy()
    state = AgentState(run_id="r1", task="x")
    events = [event async for event in strategy.stream(state)]
    assert len(events) == 1
    assert events[0].kind == "done"
    assert isinstance(events[0].content, dict)


@pytest.mark.asyncio
async def test_default_stream_runs_the_strategy() -> None:
    strategy = _NoopStrategy()
    state = AgentState(run_id="r1", task="x")
    [_ async for _ in strategy.stream(state)]
    # `run()` was called by the default impl — one step appended.
    assert len(state.steps) == 1
    assert state.steps[0].kind == "think"


@pytest.mark.asyncio
async def test_override_emits_intermediate_events() -> None:
    strategy = _OverridingStrategy()
    state = AgentState(run_id="r1", task="x")
    events = [event async for event in strategy.stream(state)]
    kinds = [event.kind for event in events]
    assert kinds == ["text", "text", "text", "done"]
    assert events[-1].kind == "done"
    assert events[2].cumulative_text == "Hello, world"


def test_override_detection_via_method_identity() -> None:
    """`ChatSession` uses `type(strategy).stream is not
    ReasoningStrategy.stream` to detect real per-token impls."""
    assert type(_NoopStrategy()).stream is ReasoningStrategy.stream
    assert type(_OverridingStrategy()).stream is not ReasoningStrategy.stream
