"""Unit tests for `StatsdHook` (feat-009 v0.2 follow-up)."""

from __future__ import annotations

import pytest
from agentforge_core.values.messages import ToolCall
from agentforge_core.values.state import RunResult, Step
from agentforge_statsd import StatsdHook
from agentforge_statsd._inmem_runner import FakeStatsdRunner


def test_step_emits_counter_and_timing() -> None:
    runner = FakeStatsdRunner()
    hook = StatsdHook(runner=runner, prefix="af.test")
    step = Step(iteration=0, kind="think", content="x", duration_ms=42)

    hook(step)

    assert ("incr", "af.test.step.think", 1.0) in runner.calls
    assert ("timing", "af.test.step.duration_ms", 42.0) in runner.calls


def test_step_with_tool_call_emits_tool_counter() -> None:
    runner = FakeStatsdRunner()
    hook = StatsdHook(runner=runner)
    step = Step(
        iteration=0,
        kind="act",
        content="x",
        duration_ms=0,
        tool_call=ToolCall(id="t-1", name="web_search", arguments={"q": "hi"}),
    )

    hook(step)

    assert ("incr", "agentforge.step.act", 1.0) in runner.calls
    assert ("incr", "agentforge.tool.web_search", 1.0) in runner.calls
    # duration_ms == 0 → no timing call
    assert not any(c[0] == "timing" for c in runner.calls)


def test_finish_emits_counters_gauges_and_timing() -> None:
    runner = FakeStatsdRunner()
    hook = StatsdHook(runner=runner, prefix="af.test")
    result = RunResult(
        output="ok",
        cost_usd=0.123,
        tokens_in=10,
        tokens_out=20,
        run_id="r-1",
        duration_ms=987,
        finish_reason="completed",
    )

    hook(result)

    keys = {c[1] for c in runner.calls}
    assert "af.test.run.finish.completed" in keys
    assert "af.test.run.duration_ms" in keys
    assert "af.test.run.cost_usd" in keys
    assert "af.test.run.tokens_in" in keys
    assert "af.test.run.tokens_out" in keys
    # Gauges carry the float values verbatim
    assert ("gauge", "af.test.run.cost_usd", 0.123) in runner.calls
    assert ("gauge", "af.test.run.tokens_in", 10.0) in runner.calls
    assert ("timing", "af.test.run.duration_ms", 987.0) in runner.calls


def test_prefix_trailing_dot_stripped() -> None:
    hook = StatsdHook(runner=FakeStatsdRunner(), prefix="af.")
    assert hook.prefix == "af"


def test_empty_prefix_rejected() -> None:
    with pytest.raises(ValueError, match="prefix is required"):
        StatsdHook(runner=FakeStatsdRunner(), prefix="")


def test_close_propagates_to_runner() -> None:
    runner = FakeStatsdRunner()
    hook = StatsdHook(runner=runner)
    hook.close()
    assert runner.closed
