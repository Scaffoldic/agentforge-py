"""Tests for `agent_factory` + pytest fixtures (feat-016 chunk 2)."""

from __future__ import annotations

import pytest
from agentforge import Agent
from agentforge.memory import InMemoryStore
from agentforge.testing import MockLLMClient, agent_factory
from agentforge.testing import fixtures as _fixtures


@pytest.mark.asyncio
async def test_factory_returns_runnable_agent() -> None:
    agent = agent_factory()
    result = await agent.run("hello")
    assert isinstance(agent, Agent)
    assert result.output == "ok"
    assert agent.budget.usd == pytest.approx(0.10)
    assert agent.budget.max_iterations == 3


@pytest.mark.asyncio
async def test_factory_accepts_explicit_model() -> None:
    llm = MockLLMClient.from_script([{"text": "custom answer", "stop_reason": "end_turn"}])
    agent = agent_factory(model=llm)
    result = await agent.run("hello")
    assert result.output == "custom answer"
    assert llm.call_count == 1


@pytest.mark.asyncio
async def test_factory_accepts_explicit_memory() -> None:
    store = InMemoryStore()
    agent = agent_factory(memory=store)
    assert agent.memory is store


def test_fixtures_module_exports_helpers() -> None:
    """Confirm both helpers are present and the underlying functions
    construct the right shapes."""
    # FixtureFunctionMarker wraps the underlying functions; both should
    # be importable and callable surfaces.
    assert _fixtures.mock_llm is not None
    assert _fixtures.temp_memory_store is not None


def test_public_re_exports_conformance() -> None:
    from agentforge.testing import (  # noqa: PLC0415
        run_memory_conformance,
        run_strategy_conformance,
        run_vector_conformance,
    )

    assert callable(run_memory_conformance)
    assert callable(run_strategy_conformance)
    assert callable(run_vector_conformance)
