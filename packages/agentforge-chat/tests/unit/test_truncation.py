"""Unit tests for truncation strategies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from agentforge_chat import Hybrid, SlidingWindow, SummariseOldest, TokenBudget
from agentforge_core.testing import run_truncation_conformance
from agentforge_core.values.chat import ChatTurn


def _make_turns(n: int, *, role: str = "user", chars: int = 20) -> list[ChatTurn]:
    base = datetime.now(UTC)
    return [
        ChatTurn(
            id=f"t{i}",
            session_id="s",
            role=role,
            content="x" * chars,
            timestamp=base + timedelta(seconds=i),
        )
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_sliding_window_conformance() -> None:
    await run_truncation_conformance(SlidingWindow(max_turns=3))


@pytest.mark.asyncio
async def test_token_budget_conformance() -> None:
    await run_truncation_conformance(TokenBudget(max_tokens=1000))


@pytest.mark.asyncio
async def test_hybrid_conformance() -> None:
    await run_truncation_conformance(Hybrid(SlidingWindow(20), TokenBudget(500)))


@pytest.mark.asyncio
async def test_summarise_oldest_conformance() -> None:
    await run_truncation_conformance(SummariseOldest(threshold_turns=2))


@pytest.mark.asyncio
async def test_sliding_window_keeps_last_n() -> None:
    turns = _make_turns(5)
    out = await SlidingWindow(max_turns=2).select(turns, "next", {})
    assert [t.id for t in out] == ["t3", "t4"]


def test_sliding_window_rejects_zero() -> None:
    with pytest.raises(ValueError, match="max_turns"):
        SlidingWindow(max_turns=0)


def test_token_budget_rejects_zero() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        TokenBudget(max_tokens=0)


@pytest.mark.asyncio
async def test_token_budget_drops_oldest_when_over_cap() -> None:
    turns = _make_turns(5, chars=200)
    # 200 chars ≈ 50 tokens per turn. cap=100 → keep ~2 turns.
    out = await TokenBudget(max_tokens=120).select(turns, "msg", {})
    assert len(out) <= 3
    assert all(t in turns for t in out)


@pytest.mark.asyncio
async def test_summarise_oldest_compresses_older_turns() -> None:
    turns = _make_turns(5)
    out = await SummariseOldest(threshold_turns=2).select(turns, "msg", {})
    # first turn is the synthesised summary
    assert out[0].role == "system"
    assert out[0].metadata.get("agentforge_chat.summary") is True
    # last two are kept verbatim
    assert out[-2].id == "t3"
    assert out[-1].id == "t4"


@pytest.mark.asyncio
async def test_summarise_oldest_passthrough_below_threshold() -> None:
    turns = _make_turns(2)
    out = await SummariseOldest(threshold_turns=3).select(turns, "msg", {})
    assert out == turns


@pytest.mark.asyncio
async def test_hybrid_pipes_through_strategies() -> None:
    turns = _make_turns(10)
    pipeline = Hybrid(SlidingWindow(5), SlidingWindow(2))
    out = await pipeline.select(turns, "msg", {})
    assert [t.id for t in out] == ["t8", "t9"]


def test_hybrid_rejects_empty() -> None:
    with pytest.raises(ValueError, match="at least one"):
        Hybrid()


@pytest.mark.asyncio
async def test_pair_atomicity_drops_orphan_tool_turn() -> None:
    base = datetime.now(UTC)
    turns = [
        ChatTurn(
            id="a",
            session_id="s",
            role="assistant",
            content="call",
            timestamp=base,
        ),
        ChatTurn(
            id="b",
            session_id="s",
            role="tool",
            content="result",
            timestamp=base + timedelta(seconds=1),
        ),
        ChatTurn(
            id="c",
            session_id="s",
            role="tool",
            content="orphan-result",
            timestamp=base + timedelta(seconds=2),
        ),
    ]
    # SlidingWindow(2) would pick [b, c]; pair-atomicity drops c
    # because it has no preceding assistant in the selection.
    out = await SlidingWindow(2).select(turns, "msg", {})
    assert "c" not in [t.id for t in out]
