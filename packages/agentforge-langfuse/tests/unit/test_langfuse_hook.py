"""Unit tests for `LangfuseHook` (feat-009 v0.2 follow-up)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from agentforge_core.production.run_context import bind_run, new_run, reset_run
from agentforge_core.values.messages import ToolCall
from agentforge_core.values.state import RunResult, Step
from agentforge_langfuse import LangfuseHook
from agentforge_langfuse._inmem_runner import FakeLangfuseRunner


@pytest.fixture
def bound_run_id() -> Iterator[str]:
    """Bind a RunContext so `current_run()` resolves inside the hook."""
    ctx = new_run(task="t")
    token = bind_run(ctx)
    try:
        yield ctx.run_id
    finally:
        reset_run(token)


def test_first_step_opens_trace_and_adds_span(bound_run_id: str) -> None:
    runner = FakeLangfuseRunner()
    hook = LangfuseHook(runner=runner, trace_name_prefix="af.test")

    hook(Step(iteration=0, kind="think", content="hello", duration_ms=10))

    rec = runner.traces[bound_run_id]
    assert rec.name == "af.test.run"
    assert rec.metadata["agentforge.run_id"] == bound_run_id
    assert len(rec.spans) == 1
    assert rec.spans[0]["name"] == "step:think"
    assert rec.spans[0]["metadata"]["iteration"] == 0
    assert rec.spans[0]["metadata"]["duration_ms"] == 10


def test_subsequent_step_reuses_trace(bound_run_id: str) -> None:
    runner = FakeLangfuseRunner()
    hook = LangfuseHook(runner=runner)
    hook(Step(iteration=0, kind="think", content="a"))
    hook(Step(iteration=1, kind="act", content="b"))

    rec = runner.traces[bound_run_id]
    assert [s["name"] for s in rec.spans] == ["step:think", "step:act"]
    assert len(runner.traces) == 1


def test_step_with_tool_call_nests_span_and_redacts(bound_run_id: str) -> None:
    runner = FakeLangfuseRunner()
    hook = LangfuseHook(runner=runner)
    step = Step(
        iteration=0,
        kind="act",
        content="x",
        tool_call=ToolCall(
            id="t-1",
            name="web_search",
            arguments={"query": "hi", "api_key": "shh"},
        ),
    )

    hook(step)

    rec = runner.traces[bound_run_id]
    tool_span = next(s for s in rec.spans if s["name"] == "tool:web_search")
    assert tool_span["metadata"]["args"]["api_key"] == "<redacted>"
    assert tool_span["metadata"]["args"]["query"] == "hi"


def test_finish_adds_scores_and_flushes(bound_run_id: str) -> None:
    runner = FakeLangfuseRunner()
    hook = LangfuseHook(runner=runner)
    hook(Step(iteration=0, kind="think", content="x"))
    hook(
        RunResult(
            output="ok",
            cost_usd=0.42,
            tokens_in=5,
            tokens_out=7,
            run_id=bound_run_id,
            duration_ms=123,
            finish_reason="completed",
        )
    )

    rec = runner.traces[bound_run_id]
    scores = {s["name"]: s for s in rec.scores}
    assert scores["cost_usd"]["value"] == 0.42
    assert "finish_reason=completed" in (scores["cost_usd"]["comment"] or "")
    assert scores["duration_ms"]["value"] == 123.0
    assert rec.flushed is True


def test_finish_without_prior_step_opens_synthetic_trace() -> None:
    runner = FakeLangfuseRunner()
    hook = LangfuseHook(runner=runner)

    hook(
        RunResult(
            output="ok",
            cost_usd=0.0,
            tokens_in=0,
            tokens_out=0,
            run_id="r-zero-step",
            duration_ms=5,
            finish_reason="completed",
        )
    )

    rec = runner.traces["r-zero-step"]
    assert rec.metadata["synthetic"] is True
    assert any(s["name"] == "cost_usd" for s in rec.scores)


def test_step_outside_run_context_is_a_noop() -> None:
    """If a caller fires the hook outside `Agent.run`, the hook
    silently drops the step instead of crashing."""
    runner = FakeLangfuseRunner()
    hook = LangfuseHook(runner=runner)
    hook(Step(iteration=0, kind="think", content="x"))
    assert runner.traces == {}


def test_empty_prefix_rejected() -> None:
    with pytest.raises(ValueError, match="trace_name_prefix is required"):
        LangfuseHook(runner=FakeLangfuseRunner(), trace_name_prefix="")


def test_close_propagates_to_runner() -> None:
    runner = FakeLangfuseRunner()
    hook = LangfuseHook(runner=runner)
    hook.close()
    assert runner.closed


def test_fake_runner_silently_drops_unknown_trace_ids() -> None:
    """Defensive: if a caller mis-routes a span/score to an unknown
    trace_id, the fake drops it silently (matches the production
    SDK's behavior of failing soft on unknown handles)."""
    runner = FakeLangfuseRunner()
    runner.add_span(trace_id="never-opened", name="x")
    runner.add_score(trace_id="never-opened", name="cost_usd", value=1.0)
    runner.flush(trace_id="never-opened")
    assert runner.traces == {}


def test_redact_fields_override_propagates() -> None:
    hook = LangfuseHook(
        runner=FakeLangfuseRunner(),
        redact_fields=("ssn", "card_number"),
    )
    assert hook.redact_fields == ("ssn", "card_number")
