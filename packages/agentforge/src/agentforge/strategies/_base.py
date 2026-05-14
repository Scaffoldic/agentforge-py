"""`StrategyBase` — shared helpers every shipped strategy inherits from.

Concrete strategies (ReAct, Plan-Execute, Tree-of-Thoughts,
Multi-Agent) inherit `StrategyBase` and implement `run(state)`.
The base class provides the three operations every strategy
performs at LLM-call boundaries:

  - `_check_guardrails(state)` — `BudgetPolicy.check()` plus
    iteration accounting. Required before every LLM call by the
    `ReasoningStrategy` invariant; the conformance suite verifies
    via AST inspection that every shipped strategy calls this
    inside its main loop.
  - `_record_step(state, kind, content, **kwargs)` — append a
    `Step` to `state.steps` with consistent shape.
  - `_call_llm(state, system, messages, tools=None)` —
    guardrail-check → LLM call → record cost on the budget →
    record `think` step → return `LLMResponse`.

The class is named `StrategyBase` (no underscore) because it is
part of the framework's *internal* public surface — strategy
authors who write custom loops are encouraged to inherit from it
to get conformance for free. (External-to-framework name without
the underscore makes it discoverable; the class is exported from
`agentforge.strategies`.)
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import abstractmethod
from typing import Any

from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.contracts.tool import Tool
from agentforge_core.observability.tracing import get_tracer
from agentforge_core.values.messages import LLMResponse, Message, ToolSpec
from agentforge_core.values.state import AgentState, Step, StepKind
from pydantic import ValidationError

from agentforge.runtime import RUNTIME_KEY, RuntimeContext

DEFAULT_TOOL_TIMEOUT_S = 30.0
"""Default per-tool execution timeout. Overridable per call to
`_dispatch_tool` and (eventually, per feat-004 §4.5) via
`agent.tool_options.timeout_s` in `agentforge.yaml`."""

log = logging.getLogger(__name__)


def get_runtime(state: AgentState) -> RuntimeContext:
    """Return the `RuntimeContext` bound on `state.metadata`.

    `Agent.run()` populates this before calling `strategy.run(state)`.
    Strategies that bypass `Agent.run()` (e.g. unit tests) must bind
    a context manually via `state.metadata[RUNTIME_KEY] = ...`.

    Raises:
        RuntimeError: no runtime context is bound (the strategy was
            invoked outside of `Agent.run()` and no test fixture set
            one up).
    """
    rt = state.metadata.get(RUNTIME_KEY)
    if rt is None:
        raise RuntimeError(
            "AgentState has no RuntimeContext bound. Strategies should "
            "be invoked via Agent.run(); tests that drive strategy.run() "
            "directly must set state.metadata[RUNTIME_KEY] = "
            "RuntimeContext(...) first."
        )
    if not isinstance(rt, RuntimeContext):
        raise TypeError(
            f"state.metadata[{RUNTIME_KEY}!r] is not a RuntimeContext: got {type(rt).__name__}"
        )
    return rt


class StrategyBase(ReasoningStrategy):
    """Abstract base for shipped reasoning strategies.

    Provides the budget-aware LLM-call helper, step recording, and
    guardrail-check primitive used by every strategy. Subclasses
    implement `run(state)`.
    """

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState: ...

    # ----------------------------------------------------------------
    # Helpers — every concrete strategy uses these.
    # ----------------------------------------------------------------

    def _check_guardrails(self, state: AgentState) -> None:
        """Run all per-iteration guardrail checks.

        Called before every LLM call. Raises `BudgetExceeded` /
        `GuardrailViolation` if a cap is breached. The conformance
        suite verifies via AST inspection that every concrete
        strategy class invokes this method inside its main loop.
        """
        runtime = get_runtime(state)
        runtime.budget.check()

    def _record_step(
        self,
        state: AgentState,
        *,
        iteration: int,
        kind: StepKind,
        content: str | dict[str, object],
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        duration_ms: int = 0,
        tool_call: object | None = None,
    ) -> Step:
        """Append a `Step` to `state.steps` with consistent shape."""
        step = Step(
            iteration=iteration,
            kind=kind,
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            tool_call=tool_call,  # type: ignore[arg-type]
        )
        state.steps.append(step)
        return step

    async def _call_llm(
        self,
        state: AgentState,
        *,
        iteration: int,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        kind: StepKind = "think",
    ) -> LLMResponse:
        """Guardrail-check → LLM call → record cost → record step.

        Centralises the four operations every shipped strategy
        performs at LLM-call boundaries. The conformance suite
        treats a class that uses this helper as having satisfied
        the guardrail-call invariant.
        """
        self._check_guardrails(state)
        runtime = get_runtime(state)
        llm: LLMClient = runtime.llm

        tracer = get_tracer()
        started_ms = time.monotonic()
        with tracer.start_as_current_span(
            "llm.call",
            attributes={
                "agentforge.iteration": iteration,
                "agentforge.llm.has_tools": tools is not None and len(tools) > 0,
            },
        ) as llm_span:
            response = await llm.call(system=system, messages=messages, tools=tools)
            llm_span.set_attribute("agentforge.llm.provider", response.provider)
            llm_span.set_attribute("agentforge.llm.model", response.model)
            llm_span.set_attribute("agentforge.llm.tokens_in", response.usage.input_tokens)
            llm_span.set_attribute("agentforge.llm.tokens_out", response.usage.output_tokens)
            llm_span.set_attribute("agentforge.llm.cost_usd", float(response.cost_usd))
            llm_span.set_attribute(
                "agentforge.llm.stop_reason",
                str(response.stop_reason),
            )
        duration_ms = int((time.monotonic() - started_ms) * 1000)

        # Record cost on the shared BudgetPolicy.
        runtime.budget.commit(response.cost_usd, response.usage.total)
        runtime.budget.increment_iteration()

        # Deliberately do NOT call record_success() here — the
        # error_streak tracks tool-execution failures across
        # iterations, not LLM-call success. Resetting on every LLM
        # call would make the streak counter useless: every iteration
        # would start with a streak reset, so a broken tool that
        # always errors would never accumulate enough errors to trip
        # the cap. Strategies call record_success() / record_error()
        # around tool dispatches themselves.

        # Append the LLM-call step to the trace.
        self._record_step(
            state,
            iteration=iteration,
            kind=kind,
            content=response.content,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=response.cost_usd,
            duration_ms=duration_ms,
        )

        return response

    async def _dispatch_tool(
        self,
        tool: Tool | None,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        timeout_s: float | None = DEFAULT_TOOL_TIMEOUT_S,
    ) -> str:
        """Validate args, run a tool with a timeout, capture errors.

        Centralises the tool-call dispatch path per feat-004 §4.3:

        1. Tool not registered → observation explaining "not registered".
        2. ValidationError on `input_schema.model_validate(arguments)`
           → observation showing what's wrong (LLM sees the validation
           error, not a stack trace, so it can self-correct on the next
           iteration).
        3. `await tool.run(**validated)` wrapped in
           `asyncio.wait_for(timeout=timeout_s)` (None disables).
        4. Any exception from the tool body → observation prefixed
           `Error:`. Tools should raise rather than catch — the
           strategy turns the raise into the LLM's observation.

        Returns the observation string. The caller decides whether to
        record a Step / increment the budget's success/error streak /
        forward to the LLM as a `tool` message.
        """
        if tool is None:
            return f"Error: tool {tool_name!r} is not registered on this agent."
        try:
            validated = tool.input_schema.model_validate(arguments)
        except ValidationError as exc:
            return f"Error: invalid arguments for {tool_name!r}: {exc}"
        kwargs = validated.model_dump()

        tracer = get_tracer()
        started_ms = time.monotonic()
        with tracer.start_as_current_span(
            f"tool.{tool_name}",
            attributes={
                "agentforge.tool.name": tool_name,
                "agentforge.tool.timeout_s": (float(timeout_s) if timeout_s is not None else -1.0),
            },
        ) as tool_span:
            try:
                if timeout_s is None:
                    raw = await tool.run(**kwargs)
                else:
                    raw = await asyncio.wait_for(tool.run(**kwargs), timeout=timeout_s)
            except TimeoutError:
                tool_span.set_attribute("agentforge.tool.error", "TimeoutError")
                return f"Error: tool {tool_name!r} exceeded timeout_s={timeout_s}."
            except Exception as exc:
                tool_span.set_attribute("agentforge.tool.error", type(exc).__name__)
                return f"Error: {type(exc).__name__}: {exc}"
            finally:
                tool_span.set_attribute(
                    "agentforge.tool.duration_ms",
                    int((time.monotonic() - started_ms) * 1000),
                )
        return raw if isinstance(raw, str) else str(raw)
