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
"""

from __future__ import annotations

from abc import ABC, abstractmethod

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
