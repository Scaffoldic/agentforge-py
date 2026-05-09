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

import logging
import time
from abc import abstractmethod

from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.messages import LLMResponse, Message, ToolSpec
from agentforge_core.values.state import AgentState, Step, StepKind

from agentforge.runtime import RUNTIME_KEY, RuntimeContext

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

        started_ms = time.monotonic()
        response = await llm.call(system=system, messages=messages, tools=tools)
        duration_ms = int((time.monotonic() - started_ms) * 1000)

        # Record cost on the shared BudgetPolicy.
        runtime.budget.commit(response.cost_usd, response.usage.total)
        runtime.budget.increment_iteration()

        # Record success unless the response contained a tool error
        # (tool dispatch happens elsewhere; LLM calls themselves don't
        # increment the error streak).
        runtime.budget.record_success()

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
