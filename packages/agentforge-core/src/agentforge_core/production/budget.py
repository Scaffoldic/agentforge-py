"""`BudgetPolicy` — per-run cost cap (per ADR-0010).

Every reasoning strategy must call `BudgetPolicy.check` before every
LLM call. Branching strategies (Tree-of-Thoughts, Multi-Agent
Supervisor in feat-002) call `reserve` before fanning out so collective
spend across parallel branches cannot exceed the cap.

The policy aggregates spend across every provider used in a run. A
multi-provider agent (e.g. reasoning model + cheap judge + embedding
model per ADR-0018) shares one policy.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentforge_core.production.exceptions import (
    BudgetExceeded,
    GuardrailViolation,
)


class BudgetPolicy(BaseModel):
    """Per-run cost and resource cap.

    Attributes:
        usd: Maximum spend in USD across all LLM/embedding providers
            used during the run. Default $1.00 — small enough that the
            naive 3-line agent never racks up surprise bills, large
            enough for a meaningful exploration.
        max_tokens: Maximum total tokens (input + output) consumed in
            the run.
        max_iterations: Maximum reasoning loop iterations.
        error_streak_limit: Maximum consecutive tool/observation errors
            before the loop aborts.
    """

    model_config = ConfigDict(strict=True, validate_assignment=True)

    usd: float = Field(default=1.0, ge=0.0)
    max_tokens: int = Field(default=200_000, ge=0)
    max_iterations: int = Field(default=25, ge=1)
    error_streak_limit: int = Field(default=3, ge=1)

    spent_usd: float = Field(default=0.0, ge=0.0)
    reserved_usd: float = Field(default=0.0, ge=0.0)
    consumed_tokens: int = Field(default=0, ge=0)
    iteration: int = Field(default=0, ge=0)
    error_streak: int = Field(default=0, ge=0)

    def remaining_usd(self) -> float:
        """USD budget left after committed spend and reservations."""
        return max(0.0, self.usd - self.spent_usd - self.reserved_usd)

    def check(self) -> None:
        """Raise if any cap is breached. Called before every LLM call.

        Raises:
            BudgetExceeded: USD or token cap exhausted.
            GuardrailViolation: iteration or error-streak limit reached.
        """
        if self.spent_usd >= self.usd:
            raise BudgetExceeded(
                f"USD budget exhausted: spent ${self.spent_usd:.4f} of ${self.usd:.4f}"
            )
        if self.consumed_tokens >= self.max_tokens:
            raise BudgetExceeded(
                f"Token budget exhausted: {self.consumed_tokens} of {self.max_tokens}"
            )
        if self.iteration >= self.max_iterations:
            raise GuardrailViolation(
                f"Iteration cap reached: {self.iteration} of {self.max_iterations}"
            )
        if self.error_streak >= self.error_streak_limit:
            raise GuardrailViolation(
                f"Error streak limit hit: {self.error_streak} consecutive errors"
            )

    def reserve(self, usd: float) -> None:
        """Pre-reserve USD budget for a planned spend.

        Used by branching strategies that fan out: each branch reserves
        before issuing the LLM call so the sum of reservations cannot
        exceed the cap.

        Raises:
            ValueError: `usd` is negative.
            BudgetExceeded: reservation would exceed remaining budget.
        """
        if usd < 0:
            raise ValueError(f"Cannot reserve negative budget: {usd}")
        if self.spent_usd + self.reserved_usd + usd > self.usd:
            raise BudgetExceeded(
                f"Cannot reserve ${usd:.4f}; only ${self.remaining_usd():.4f} "
                f"of ${self.usd:.4f} remains"
            )
        self.reserved_usd += usd

    def commit(self, actual_usd: float, tokens: int = 0) -> None:
        """Record actual cost after a call completes.

        Reservations are released by `release_reservation` separately;
        commit only records spend.

        Raises:
            ValueError: negative cost or token count.
        """
        if actual_usd < 0:
            raise ValueError(f"Cannot commit negative cost: {actual_usd}")
        if tokens < 0:
            raise ValueError(f"Cannot commit negative tokens: {tokens}")
        self.spent_usd += actual_usd
        self.consumed_tokens += tokens

    def release_reservation(self, usd: float) -> None:
        """Release a previously-reserved budget (e.g. on cancellation).

        Idempotent at zero — releasing more than reserved clamps to 0.
        """
        if usd < 0:
            raise ValueError(f"Cannot release negative reservation: {usd}")
        self.reserved_usd = max(0.0, self.reserved_usd - usd)

    def increment_iteration(self) -> None:
        """Record one strategy iteration. Called by the strategy loop."""
        self.iteration += 1

    def record_error(self) -> None:
        """Increment the error streak counter."""
        self.error_streak += 1

    def record_success(self) -> None:
        """Reset the error streak counter."""
        self.error_streak = 0
