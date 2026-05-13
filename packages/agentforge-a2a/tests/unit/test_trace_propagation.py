"""Unit tests for A2A W3C TraceContext propagation (feat-009 v0.3 polish).

Covers the client-side injection (`traceparent` header derived from
the active span) and the server-side extraction (the `a2a.call`
span stitches into the caller's trace).
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from agentforge import EnvBearerAuth
from agentforge.agent import Agent
from agentforge_a2a import A2AServer
from agentforge_a2a.client import _build_headers
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolSpec,
)
from agentforge_core.values.state import AgentState
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture(autouse=True)
def _reset_provider() -> None:
    """Reset OTel's process-global provider so each test starts fresh."""
    trace._TRACER_PROVIDER_SET_ONCE = trace.Once()  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]


def _install_inmemory_provider() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


class _NoAuth:
    """ClientAuth duck-type for `_build_headers` (no Bearer header)."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}


def test_build_headers_injects_traceparent_when_span_active() -> None:
    _install_inmemory_provider()
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("caller"):
        headers = _build_headers(_NoAuth(), budget_usd=None)  # type: ignore[arg-type]
    assert "traceparent" in headers
    # W3C traceparent format: `00-<trace_id>-<span_id>-<flags>`
    parts = headers["traceparent"].split("-")
    assert len(parts) == 4
    assert parts[0] == "00"


def test_build_headers_omits_traceparent_when_no_span() -> None:
    _install_inmemory_provider()
    headers = _build_headers(_NoAuth(), budget_usd=None)  # type: ignore[arg-type]
    # No active span → propagator emits nothing.
    assert "traceparent" not in headers


class _NoopStrategy(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        return state


class _FakeLLM(LLMClient):
    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        del system, messages, tools
        return LLMResponse(
            content="",
            tool_calls=(),
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=0, output_tokens=0),
            cost_usd=0.0,
            model="x",
            provider="x",
        )

    async def close(self) -> None:
        return None


def test_server_stitches_into_callers_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    exporter = _install_inmemory_provider()
    monkeypatch.setenv("A2A_TOKENS", "ok")
    agent = Agent(model=_FakeLLM(), strategy=_NoopStrategy())
    server = A2AServer(
        agent=agent,
        auth=EnvBearerAuth("A2A_TOKENS"),
        endpoints=["echo"],
    )

    # Caller-side trace: open a span, build a traceparent, fire the request.
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("caller-span") as caller_span:
        caller_trace_id = caller_span.get_span_context().trace_id
        headers = _build_headers(_NoAuth(), budget_usd=None)  # type: ignore[arg-type]

    headers["Authorization"] = "Bearer ok"

    with TestClient(server.app) as http:
        r = http.post(
            "/a2a/v1/calls",
            json={"endpoint": "echo", "payload": {}},
            headers=headers,
        )
    assert r.status_code == 200

    finished = exporter.get_finished_spans()
    a2a_spans = [s for s in finished if s.name == "a2a.call"]
    assert len(a2a_spans) == 1
    # The server-side a2a.call span shares the caller's trace_id.
    assert a2a_spans[0].context.trace_id == caller_trace_id


def _silence(logger_name: str) -> None:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)


def _suppress_a2a_logs() -> Any:
    _silence("agentforge_a2a.server")
    _silence("agentforge.observability")
    return None
