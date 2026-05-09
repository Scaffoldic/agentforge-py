"""Unit tests for `BudgetPolicy`."""

from __future__ import annotations

import pytest
from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.production.exceptions import (
    BudgetExceeded,
    GuardrailViolation,
)
from hypothesis import given, settings
from hypothesis import strategies as st


def test_default_construction() -> None:
    b = BudgetPolicy()
    assert b.usd == 1.0
    assert b.max_tokens == 200_000
    assert b.max_iterations == 25
    assert b.error_streak_limit == 3
    assert b.spent_usd == 0.0
    assert b.reserved_usd == 0.0
    assert b.consumed_tokens == 0
    assert b.iteration == 0
    assert b.error_streak == 0


def test_check_passes_at_construction() -> None:
    b = BudgetPolicy()
    b.check()


def test_remaining_usd_initial() -> None:
    b = BudgetPolicy(usd=2.0)
    assert b.remaining_usd() == pytest.approx(2.0)


def test_remaining_usd_after_spend_and_reserve() -> None:
    b = BudgetPolicy(usd=2.0)
    b.commit(0.4)
    b.reserve(0.6)
    assert b.remaining_usd() == pytest.approx(1.0)


def test_remaining_usd_clamps_to_zero() -> None:
    b = BudgetPolicy(usd=1.0)
    b.commit(1.5)
    assert b.remaining_usd() == 0.0


def test_check_raises_budget_exceeded_on_usd_exhaustion() -> None:
    b = BudgetPolicy(usd=1.0)
    b.commit(1.0)
    with pytest.raises(BudgetExceeded, match="USD budget exhausted"):
        b.check()


def test_check_raises_budget_exceeded_on_token_exhaustion() -> None:
    b = BudgetPolicy(usd=10.0, max_tokens=100)
    b.commit(0.0, tokens=100)
    with pytest.raises(BudgetExceeded, match="Token budget"):
        b.check()


def test_check_raises_guardrail_on_iteration_cap() -> None:
    b = BudgetPolicy(usd=10.0, max_iterations=2)
    b.increment_iteration()
    b.increment_iteration()
    with pytest.raises(GuardrailViolation, match="Iteration cap"):
        b.check()


def test_check_raises_guardrail_on_error_streak() -> None:
    b = BudgetPolicy(usd=10.0, error_streak_limit=2)
    b.record_error()
    b.record_error()
    with pytest.raises(GuardrailViolation, match="Error streak"):
        b.check()


def test_record_success_resets_error_streak() -> None:
    b = BudgetPolicy(error_streak_limit=3)
    b.record_error()
    b.record_error()
    b.record_success()
    assert b.error_streak == 0


def test_reserve_reduces_remaining() -> None:
    b = BudgetPolicy(usd=2.0)
    b.reserve(0.5)
    assert b.reserved_usd == pytest.approx(0.5)
    assert b.remaining_usd() == pytest.approx(1.5)


def test_reserve_negative_raises_value_error() -> None:
    b = BudgetPolicy()
    with pytest.raises(ValueError, match="negative"):
        b.reserve(-0.1)


def test_reserve_exceeding_remaining_raises_budget_exceeded() -> None:
    b = BudgetPolicy(usd=1.0)
    b.reserve(0.6)
    with pytest.raises(BudgetExceeded, match="Cannot reserve"):
        b.reserve(0.5)


def test_commit_records_spent_and_tokens() -> None:
    b = BudgetPolicy()
    b.commit(0.25, tokens=100)
    assert b.spent_usd == pytest.approx(0.25)
    assert b.consumed_tokens == 100


def test_commit_negative_usd_raises() -> None:
    b = BudgetPolicy()
    with pytest.raises(ValueError, match="negative cost"):
        b.commit(-0.1)


def test_commit_negative_tokens_raises() -> None:
    b = BudgetPolicy()
    with pytest.raises(ValueError, match="negative tokens"):
        b.commit(0.0, tokens=-1)


def test_release_reservation_reduces_reserved() -> None:
    b = BudgetPolicy(usd=2.0)
    b.reserve(0.5)
    b.release_reservation(0.3)
    assert b.reserved_usd == pytest.approx(0.2)


def test_release_reservation_clamps_to_zero() -> None:
    b = BudgetPolicy(usd=2.0)
    b.reserve(0.2)
    b.release_reservation(0.5)
    assert b.reserved_usd == 0.0


def test_release_reservation_negative_raises() -> None:
    b = BudgetPolicy()
    with pytest.raises(ValueError, match="negative reservation"):
        b.release_reservation(-0.1)


def test_increment_iteration() -> None:
    b = BudgetPolicy()
    b.increment_iteration()
    b.increment_iteration()
    assert b.iteration == 2


@given(
    cap=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
    operations=st.lists(
        st.tuples(
            st.sampled_from(["reserve", "commit", "release"]),
            st.floats(min_value=0.0, max_value=10.0, allow_nan=False),
        ),
        max_size=20,
    ),
)
@settings(max_examples=50, deadline=None)
def test_property_invariant_spent_plus_reserved_never_exceeds_cap(
    cap: float, operations: list[tuple[str, float]]
) -> None:
    """For any sequence of (reserve, commit, release) operations, spent +
    reserved stays within cap or raises BudgetExceeded."""
    b = BudgetPolicy(usd=cap)
    for op, amount in operations:
        try:
            if op == "reserve":
                b.reserve(amount)
            elif op == "commit":
                b.commit(amount)
            else:
                b.release_reservation(amount)
        except BudgetExceeded:
            pass
        # invariant: never exceed cap when budget is healthy
        if b.spent_usd + b.reserved_usd > cap + 1e-9:
            # commit can exceed (records actual past spend that overran);
            # reservation cannot — that's the only case allowed to over-cap
            assert b.spent_usd > cap or b.spent_usd + b.reserved_usd <= cap + 1e-9
