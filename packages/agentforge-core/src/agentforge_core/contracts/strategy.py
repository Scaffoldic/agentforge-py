"""`ReasoningStrategy` — the locked reasoning-loop ABC.

feat-001 ships only the contract. feat-002 ships `ReActLoop` (the stable
default) and three experimental loops (`PlanExecuteLoop`,
`TreeOfThoughts`, `MultiAgentSupervisor`).

Every concrete strategy honours these invariants (enforced by the
conformance suite in feat-002):

  - Guardrails (`BudgetPolicy.check`) are called before every LLM call.
  - All state flows through one shared `AgentState` — no module globals.
  - Every reasoning step is appended to `state.steps`.
  - Termination is one of: finish signal, max_iterations, guardrail trip.

feat-020 v0.2 adds a non-abstract `stream()` default that wraps
`run()` and emits a single terminal `done` `StreamingEvent` so
existing concrete strategies keep working unchanged. Strategies
that want real per-token (or per-step) streaming override it to
yield events as the LLM emits tokens. `ChatSession.stream()`
detects the override and forwards events to the wire.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from agentforge_core.values.chat import StreamingEvent
from agentforge_core.values.state import AgentState


class ReasoningStrategy(ABC):
    """Drives the agent from initial task to terminal state."""

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Execute the reasoning loop until termination.

        Args:
            state: The mutable per-run state.

        Returns:
            The same `AgentState` instance with `steps` populated.
        """

    async def stream(self, state: AgentState) -> AsyncIterator[StreamingEvent]:
        """Drive the agent and yield `StreamingEvent` frames as they arrive.

        Default implementation: call `run(state)` to completion, then
        yield exactly one `done` event carrying the run-level summary.
        Backward-compatible — every existing strategy gets a working
        `stream()` for free, and `ChatSession.stream()` falls back to
        the v0.1 buffer-then-stream path when this default is in
        effect.

        Concrete strategies that want per-token streaming override
        this and yield `text` / `tool_call` / `tool_result` /
        `thinking` events as the LLM produces them, then a terminal
        `done` event. `ChatSession.stream()` detects the override
        via `type(strategy).stream is not ReasoningStrategy.stream`
        and switches to forwarding events directly to the wire.
        """
        result = await self.run(state)
        yield StreamingEvent(
            kind="done",
            content={
                "run_id": getattr(result, "run_id", ""),
                "cost_usd": float(getattr(result, "cost_usd", 0.0) or 0.0),
            },
        )
