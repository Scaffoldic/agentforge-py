"""Unit tests for `agentforge_otel.hook.OpenTelemetryHook`.

Uses OTel's `InMemorySpanExporter` so we can assert on the actual
spans the framework + hook produce, without sending traffic anywhere.
"""

from __future__ import annotations

import logging

import agentforge_otel.hook as hook_mod
import pytest
from agentforge import Agent
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.messages import ToolCall
from agentforge_core.values.state import AgentState, RunResult, Step
from agentforge_otel import OpenTelemetryHook
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture(autouse=True)
def _reset_provider_state():
    """Reset the module-level "provider installed" flag + tracer
    provider so each test starts clean. OTel's `set_tracer_provider`
    refuses to swap once set, so we reset the internals.
    """
    hook_mod._provider_installed[0] = False
    trace._TRACER_PROVIDER_SET_ONCE = trace.Once()  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]


def _install_inmemory_provider() -> InMemorySpanExporter:
    """Replace OTel's provider with one that exports to an in-memory
    list. Returns the exporter so tests can inspect emitted spans."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    hook_mod._provider_installed[0] = True
    return exporter


# --- construction ---------------------------------------------------


def test_invalid_sample_rate_rejected():
    with pytest.raises(ValueError, match="sample_rate"):
        OpenTelemetryHook(service_name="t", sample_rate=1.5)
    with pytest.raises(ValueError, match="sample_rate"):
        OpenTelemetryHook(service_name="t", sample_rate=-0.1)


def test_missing_service_name_rejected():
    with pytest.raises(ValueError, match="service_name"):
        OpenTelemetryHook(service_name="")


def test_construction_idempotent_does_not_replace_provider():
    """If a provider is already installed, the hook doesn't clobber it."""
    exporter = _install_inmemory_provider()
    existing_provider = trace.get_tracer_provider()

    OpenTelemetryHook(service_name="agent-1", endpoint="http://nowhere:4317")
    # Provider unchanged — installation respected the existing one.
    assert trace.get_tracer_provider() is existing_provider
    assert exporter is not None  # exporter still wired


# --- step events ---------------------------------------------------


def test_step_event_added_to_current_span():
    exporter = _install_inmemory_provider()
    h = OpenTelemetryHook(service_name="test", endpoint="http://localhost:4317")

    tracer = trace.get_tracer("agentforge")
    with tracer.start_as_current_span("agent.run"):
        h(
            Step(
                iteration=0,
                kind="observe",
                content="hello",
                tokens_in=10,
                tokens_out=20,
                cost_usd=0.001,
                duration_ms=42,
            )
        )

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    events = list(finished[0].events)
    step_events = [e for e in events if e.name == "agent.step"]
    assert len(step_events) == 1
    attrs = dict(step_events[0].attributes or {})
    assert attrs["agentforge.step.iteration"] == 0
    assert attrs["agentforge.step.kind"] == "observe"
    assert attrs["agentforge.step.cost_usd"] == pytest.approx(0.001)
    assert attrs["agentforge.step.tokens_in"] == 10


def test_tool_call_event_added_with_redaction():
    exporter = _install_inmemory_provider()
    h = OpenTelemetryHook(service_name="test", endpoint="http://localhost:4317")

    tracer = trace.get_tracer("agentforge")
    with tracer.start_as_current_span("agent.run"):
        h(
            Step(
                iteration=0,
                kind="act",
                content="call",
                tool_call=ToolCall(
                    id="01TEST",
                    name="charge_customer",
                    arguments={
                        "customer_id": "cust_42",
                        "api_key": "sk-secret-xyz",
                        "amount_cents": 1000,
                    },
                ),
            )
        )

    finished = exporter.get_finished_spans()
    events = [e for e in finished[0].events if e.name == "agent.tool_call"]
    assert len(events) == 1
    attrs = dict(events[0].attributes or {})
    args_str = str(attrs["agentforge.tool.args"])
    assert "customer_id=" in args_str
    assert "amount_cents=" in args_str
    # api_key value redacted; key still visible.
    assert "api_key=<redacted>" in args_str
    assert "sk-secret-xyz" not in args_str


def test_custom_redact_fields_take_effect():
    exporter = _install_inmemory_provider()
    h = OpenTelemetryHook(
        service_name="test", endpoint="http://localhost:4317", redact_fields=("ssn",)
    )

    tracer = trace.get_tracer("agentforge")
    with tracer.start_as_current_span("agent.run"):
        h(
            Step(
                iteration=0,
                kind="act",
                content="x",
                tool_call=ToolCall(
                    id="01T",
                    name="lookup",
                    arguments={"ssn": "123-45-6789", "api_key": "still-visible"},
                ),
            )
        )

    finished = exporter.get_finished_spans()
    event = next(e for e in finished[0].events if e.name == "agent.tool_call")
    args_str = str(dict(event.attributes or {})["agentforge.tool.args"])
    assert "ssn=<redacted>" in args_str
    # api_key no longer in the redact list — visible.
    assert "still-visible" in args_str


# --- finish handling ----------------------------------------------


def test_finish_emits_summary_log(caplog):
    caplog.set_level(logging.INFO, logger="agentforge.observability")
    h = OpenTelemetryHook(service_name="test", endpoint="http://localhost:4317")

    result = RunResult(
        output="done",
        cost_usd=0.05,
        tokens_in=100,
        tokens_out=50,
        run_id="01HXFINISH",
        duration_ms=1234,
        finish_reason="completed",
    )
    h(result)

    msgs = [r.message for r in caplog.records]
    assert any("01HXFINISH" in m and "completed" in m and "$0.0500" in m for m in msgs)


# --- public properties --------------------------------------------


def test_public_properties():
    h = OpenTelemetryHook(
        service_name="my-agent",
        endpoint="http://localhost:4317",
        redact_fields=("custom",),
    )
    assert h.service_name == "my-agent"
    assert h.redact_fields == ("custom",)


# --- end-to-end with Agent --------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_root_span_from_agent_run():
    """Construct an Agent, run it with the OTel hook installed, assert
    the framework's `agent.run` root span landed in the exporter with
    the right attributes."""
    exporter = _install_inmemory_provider()

    class _OneStep(ReasoningStrategy):
        async def run(self, state: AgentState) -> AgentState:
            state.steps.append(Step(iteration=0, kind="observe", content="hi"))
            return state

    otel = OpenTelemetryHook(service_name="test", endpoint="http://localhost:4317")
    async with Agent(strategy=_OneStep(), on_step=otel, on_finish=otel) as agent:
        await agent.run("the task")

    finished = exporter.get_finished_spans()
    run_spans = [s for s in finished if s.name == "agent.run"]
    assert len(run_spans) == 1
    attrs = dict(run_spans[0].attributes or {})
    assert attrs["agentforge.task"] == "the task"
    assert attrs["agentforge.finish_reason"] == "completed"
    assert attrs["agentforge.n_steps"] == 1
    # The step hook annotated the span with an event.
    step_events = [e for e in run_spans[0].events if e.name == "agent.step"]
    assert len(step_events) == 1
