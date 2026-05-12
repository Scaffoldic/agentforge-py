"""Unit tests for `agent_call_stream` (feat-014 v0.2)."""

from __future__ import annotations

import asyncio

import pytest
from agentforge_a2a import (
    A2APeer,
    A2APeerConfig,
    agent_call_stream,
)
from agentforge_a2a._inmem_runner import FakeA2AClientRunner
from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.production.exceptions import A2AAuthError, A2ACallError, ModuleError


def _peer(runner: FakeA2AClientRunner) -> A2APeer:
    config = A2APeerConfig(
        name="alpha",
        url="https://alpha.example/a2a/v1/calls",
        auth={"type": "bearer", "token": "tok"},
    )
    return A2APeer.from_config(config, runner=runner)


def test_stream_yields_step_chunks_then_done() -> None:
    runner = FakeA2AClientRunner(
        responses_stream=[
            {"kind": "step", "step": {"iteration": 0, "kind": "think", "content": "a"}},
            {"kind": "tool_call", "step": {"iteration": 1, "kind": "act", "content": "b"}},
            {"kind": "done", "content": {"output": "ok", "cost_usd": 0.0}, "run_id": "r"},
        ]
    )
    peers = {"alpha": _peer(runner)}

    async def _collect() -> list[str]:
        return [
            chunk.kind
            async for chunk in agent_call_stream(
                "alpha:verify",
                {"x": 1},
                peers=peers,
                budget_usd=0.05,
            )
        ]

    kinds = asyncio.run(_collect())
    assert kinds == ["step", "tool_call", "done"]
    # Stream URL is derived from peer.url + "/stream".
    assert runner.stream_calls[0].url == "https://alpha.example/a2a/v1/calls/stream"
    # Bearer header propagated.
    assert runner.stream_calls[0].headers["Authorization"] == "Bearer tok"
    # Budget hint header propagated.
    assert runner.stream_calls[0].headers["X-AgentForge-Budget-Usd"] == "0.050000"


def test_stream_commits_actual_cost_at_done() -> None:
    runner = FakeA2AClientRunner(
        responses_stream=[
            {"kind": "done", "content": {"output": "ok", "cost_usd": 0.0123}, "run_id": "r"},
        ]
    )
    peers = {"alpha": _peer(runner)}
    budget = BudgetPolicy(usd=1.0, max_tokens=1000, max_iterations=10)

    async def _drain() -> None:
        async for _ in agent_call_stream(
            "alpha:verify",
            {},
            peers=peers,
            budget=budget,
            budget_usd=0.05,
        ):
            pass

    asyncio.run(_drain())
    # Actual cost was committed; reservation was released.
    assert budget.spent_usd == pytest.approx(0.0123)
    assert budget.reserved_usd == 0.0


def test_stream_error_chunk_raises_call_error() -> None:
    runner = FakeA2AClientRunner(
        responses_stream=[
            {
                "kind": "error",
                "content": {"error": "RuntimeError", "message": "boom"},
            }
        ]
    )
    peers = {"alpha": _peer(runner)}
    budget = BudgetPolicy(usd=1.0, max_tokens=1000, max_iterations=10)

    async def _drain() -> None:
        async for _ in agent_call_stream(
            "alpha:verify",
            {},
            peers=peers,
            budget=budget,
            budget_usd=0.05,
        ):
            pass

    with pytest.raises(A2ACallError, match="boom"):
        asyncio.run(_drain())
    # Reservation released on failure.
    assert budget.reserved_usd == 0.0


def test_stream_auth_error_chunk_raises_auth_error() -> None:
    runner = FakeA2AClientRunner(
        responses_stream=[
            {
                "kind": "error",
                "content": {"error": "unauthorized", "message": "bad token"},
            }
        ]
    )
    peers = {"alpha": _peer(runner)}

    async def _drain() -> None:
        async for _ in agent_call_stream("alpha:verify", {}, peers=peers):
            pass

    with pytest.raises(A2AAuthError, match="bad token"):
        asyncio.run(_drain())


def test_stream_unknown_peer_raises_module_error() -> None:
    async def _drain() -> None:
        async for _ in agent_call_stream("nope:verify", {}, peers={}):
            pass

    with pytest.raises(ModuleError, match="unknown a2a peer"):
        asyncio.run(_drain())
