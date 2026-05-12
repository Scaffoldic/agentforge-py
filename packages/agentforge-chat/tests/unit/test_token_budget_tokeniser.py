"""`TokenBudget` provider-aware tokeniser tests (feat-020 v0.2)."""

from __future__ import annotations

import pytest
from agentforge_chat import TokenBudget, Tokeniser
from agentforge_core.values.chat import ChatTurn


def _turn(role: str, content: str) -> ChatTurn:
    return ChatTurn(id=f"t-{role}", session_id="s", role=role, content=content)


@pytest.mark.asyncio
async def test_token_budget_uses_supplied_tokeniser_for_turn_costs() -> None:
    """Each call to the supplied tokeniser counts as one 'token-unit'
    here — gives us a deterministic accounting we can assert on."""
    calls: list[str] = []

    def fake_tokeniser(text: str) -> int:
        calls.append(text)
        return 10  # every input costs exactly 10 tokens

    budget = TokenBudget(max_tokens=25, tokeniser=fake_tokeniser)
    turns = [_turn("user", f"msg-{i}") for i in range(5)]
    selected = await budget.select(turns, "next", {})
    # next message reserves 10; remaining = 15 → fits one turn (10).
    assert [t.id for t in selected] == [turns[-1].id]
    # tokeniser invoked at least once for next message + each evaluated
    # turn from the tail.
    assert calls[0] == "next"
    assert any(call.startswith("msg-") for call in calls[1:])


@pytest.mark.asyncio
async def test_token_budget_falls_back_to_heuristic_without_tokeniser() -> None:
    """v0.1 behaviour preserved when no tokeniser is supplied."""
    budget = TokenBudget(max_tokens=100)
    # Heuristic: 4 chars ≈ 1 token. 'abcd' = 1; 'abcdefgh' = 2.
    turns = [_turn("user", "a" * 200), _turn("assistant", "b" * 4)]
    selected = await budget.select(turns, "x", {})
    # 'x' reserves 1; assistant turn costs 1; user turn costs 50.
    # Total fits inside 100; both selected (in original order).
    assert [t.id for t in selected] == [turns[0].id, turns[1].id]


def test_tokeniser_is_a_callable_type_alias() -> None:
    """Smoke: `Tokeniser` is a Callable[[str], int] alias users can
    target. Any callable matching the signature is accepted."""

    def custom(text: str) -> int:
        return len(text)

    counter: Tokeniser = custom
    assert counter("abc") == 3
