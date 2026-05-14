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


@pytest.mark.asyncio
async def test_child_span_tree_via_react_loop():
    """Drive an Agent with the built-in ReActLoop strategy and a
    scripted FakeLLM that triggers one tool_call. Assert the full
    OTel span tree lands:
      agent.run
        ├── strategy.iteration (iter 0)
        │   ├── llm.call
        │   └── tool.<name>
        └── strategy.iteration (iter 1)
            └── llm.call
    """
    from agentforge._testing import FakeLLMClient  # noqa: PLC0415
    from agentforge.strategies.react import ReActLoop  # noqa: PLC0415
    from agentforge_core.contracts.tool import Tool  # noqa: PLC0415
    from agentforge_core.values.messages import LLMResponse, TokenUsage  # noqa: PLC0415
    from pydantic import BaseModel  # noqa: PLC0415

    exporter = _install_inmemory_provider()

    class _SearchArgs(BaseModel):
        query: str

    class _SearchTool(Tool):
        name = "search"
        description = "echoes the query"
        input_schema = _SearchArgs

        async def run(self, query: str) -> str:
            return f"got {query!r}"

    fake = FakeLLMClient(
        responses=[
            LLMResponse(
                content="I'll search.",
                stop_reason="tool_use",
                tool_calls=(ToolCall(id="t-1", name="search", arguments={"query": "x"}),),
                usage=TokenUsage(input_tokens=5, output_tokens=3),
                cost_usd=0.0,
                model="fake",
                provider="fake",
            ),
            LLMResponse(
                content="done",
                stop_reason="end_turn",
                usage=TokenUsage(input_tokens=4, output_tokens=2),
                cost_usd=0.0,
                model="fake",
                provider="fake",
            ),
        ],
    )
    otel = OpenTelemetryHook(service_name="test", endpoint="http://localhost:4317")
    async with Agent(
        model=fake,
        tools=[_SearchTool()],
        strategy=ReActLoop(),
        on_step=otel,
        on_finish=otel,
    ) as agent:
        await agent.run("find x")

    finished = exporter.get_finished_spans()
    by_name: dict[str, list] = {}
    for s in finished:
        by_name.setdefault(s.name, []).append(s)

    # Root span
    assert len(by_name["agent.run"]) == 1
    # Two iterations: one with the tool_call, one terminating
    assert len(by_name["strategy.iteration"]) == 2
    # Two LLM calls (one per iteration)
    assert len(by_name["llm.call"]) == 2
    # One tool execution
    assert len(by_name["tool.search"]) == 1
    # llm.call spans carry provider + token attributes
    llm_attrs = dict(by_name["llm.call"][0].attributes or {})
    assert llm_attrs["agentforge.llm.provider"] == "fake"
    assert llm_attrs["agentforge.llm.tokens_in"] == 5


@pytest.mark.asyncio
async def test_child_span_tree_via_tot_strategy():
    """Drive an Agent with the built-in ``TreeOfThoughts`` strategy
    and assert ``strategy.iteration`` spans land under ``agent.run``
    with ``agentforge.strategy=tot``.
    """
    from agentforge._testing import FakeLLMClient  # noqa: PLC0415
    from agentforge.strategies.tot import TreeOfThoughts  # noqa: PLC0415
    from agentforge_core.values.messages import LLMResponse, TokenUsage  # noqa: PLC0415

    exporter = _install_inmemory_provider()

    def _resp(content: str) -> LLMResponse:
        return LLMResponse(
            content=content,
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=5, output_tokens=3),
            cost_usd=0.0,
            model="fake",
            provider="fake",
        )

    fake = FakeLLMClient(
        responses=[
            _resp('{"thoughts": [{"id": "t1", "content": "thought 1"}]}'),
            _resp('{"scores": [{"branch_id": "t1", "score": 0.9, "reasoning": "ok"}]}'),
            _resp("Final answer."),
        ]
    )
    otel = OpenTelemetryHook(service_name="test", endpoint="http://localhost:4317")
    async with Agent(
        model=fake,
        tools=[],
        strategy=TreeOfThoughts(branch_factor=1, depth=1, score_threshold=0.5),
        on_step=otel,
        on_finish=otel,
    ) as agent:
        await agent.run("solve x")

    finished = exporter.get_finished_spans()
    by_name: dict[str, list] = {}
    for s in finished:
        by_name.setdefault(s.name, []).append(s)

    assert len(by_name["agent.run"]) == 1
    assert len(by_name["strategy.iteration"]) == 1
    attrs = dict(by_name["strategy.iteration"][0].attributes or {})
    assert attrs["agentforge.strategy"] == "tot"
    assert attrs["agentforge.iteration"] == 0


@pytest.mark.asyncio
async def test_child_span_tree_via_multi_agent_strategy():
    """Drive an Agent with the built-in ``MultiAgentSupervisor`` and
    assert ``strategy.iteration`` spans land with
    ``agentforge.strategy=multi_agent``.
    """
    from agentforge._testing import FakeLLMClient  # noqa: PLC0415
    from agentforge.strategies._base import get_runtime  # noqa: PLC0415
    from agentforge.strategies.multi_agent import MultiAgentSupervisor  # noqa: PLC0415
    from agentforge_core.contracts.strategy import ReasoningStrategy  # noqa: PLC0415
    from agentforge_core.values.messages import LLMResponse, TokenUsage  # noqa: PLC0415
    from agentforge_core.values.state import Step as StepCls  # noqa: PLC0415

    exporter = _install_inmemory_provider()

    class _Worker(ReasoningStrategy):
        async def run(self, state):
            get_runtime(state).budget.check()
            state.steps.append(StepCls(iteration=1, kind="synthesize", content="ok", cost_usd=0.0))
            return state

    def _resp(content: str) -> LLMResponse:
        return LLMResponse(
            content=content,
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=5, output_tokens=3),
            cost_usd=0.0,
            model="fake",
            provider="fake",
        )

    fake = FakeLLMClient(
        responses=[
            _resp('{"assignments": [{"worker": "a", "task": "subtask 1"}]}'),
            _resp("aggregated answer."),
        ]
    )
    otel = OpenTelemetryHook(service_name="test", endpoint="http://localhost:4317")
    async with Agent(
        model=fake,
        tools=[],
        strategy=MultiAgentSupervisor(workers={"a": _Worker()}, max_rounds=1),
        on_step=otel,
        on_finish=otel,
    ) as agent:
        await agent.run("big task")

    finished = exporter.get_finished_spans()
    by_name: dict[str, list] = {}
    for s in finished:
        by_name.setdefault(s.name, []).append(s)

    assert len(by_name["agent.run"]) == 1
    assert len(by_name["strategy.iteration"]) == 1
    attrs = dict(by_name["strategy.iteration"][0].attributes or {})
    assert attrs["agentforge.strategy"] == "multi_agent"
    assert attrs["agentforge.iteration"] == 0


# --- content-based PII redaction (feat-009 v0.3 polish) --------


def test_redact_value_patterns_masks_matching_values() -> None:
    """Values matching any regex in `redact_value_patterns` get
    replaced wholesale — even when the key isn't in
    `redact_fields`."""
    h = OpenTelemetryHook(
        service_name="test",
        endpoint="http://localhost:4317",
        redact_value_patterns=(
            r"\b\d{3}-\d{2}-\d{4}\b",  # US SSN
            r"\b\d{16}\b",  # Credit-card-like 16-digit run
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # email
        ),
    )
    rendered = h._redact(
        {
            "ssn": "123-45-6789",
            "card": "4111111111111111",
            "email": "alice@example.com",
            "innocent": "hello world",
            "count": 7,
        }
    )
    assert "ssn=<redacted>" in rendered
    assert "card=<redacted>" in rendered
    assert "email=<redacted>" in rendered
    # Plain integers + harmless strings pass through.
    assert "innocent='hello world'" in rendered
    assert "count=7" in rendered


def test_redact_value_patterns_default_none_is_passthrough() -> None:
    """Without `redact_value_patterns`, behaviour is identical to
    v0.1 (key-only redaction)."""
    h = OpenTelemetryHook(service_name="test", endpoint="http://localhost:4317")
    assert h.redact_value_patterns == ()
    rendered = h._redact({"email": "alice@example.com", "api_key": "shh"})
    assert "email='alice@example.com'" in rendered
    assert "api_key=<redacted>" in rendered


def test_redact_key_match_takes_precedence_over_value_match() -> None:
    h = OpenTelemetryHook(
        service_name="test",
        endpoint="http://localhost:4317",
        redact_value_patterns=(r"unused-pattern",),
    )
    rendered = h._redact({"api_key": "abc"})
    # Key matches first; we never even check the value patterns.
    assert "api_key=<redacted>" in rendered
