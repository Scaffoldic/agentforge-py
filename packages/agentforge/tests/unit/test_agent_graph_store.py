"""Unit tests for `Agent`'s `graph_store` integration (feat-009 chunk 5)."""

from __future__ import annotations

import pytest
from agentforge import Agent, InMemoryGraphStore
from agentforge._testing import FakeLLMClient
from agentforge.strategies._base import get_runtime
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.graph import GraphEdge, GraphNode
from agentforge_core.values.state import AgentState, Step


class _GraphStrategy(ReasoningStrategy):
    """Test strategy that traverses the graph_store and surfaces the
    farthest-reachable node id on the last step."""

    async def run(self, state: AgentState) -> AgentState:
        runtime = get_runtime(state)
        if runtime.graph_store is None:
            state.steps.append(Step(iteration=0, kind="observe", content="no graph_store"))
            return state
        paths = await runtime.graph_store.traverse(state.task, max_depth=3)
        farthest = paths[-1].nodes[-1].id if paths else "(no paths)"
        state.steps.append(Step(iteration=0, kind="observe", content=farthest))
        return state


# ---- Constructor wiring ----


def test_agent_without_graph_store_keyword_defaults_to_none() -> None:
    """Existing callers that don't pass `graph_store=` keep working."""
    agent = Agent(strategy=_GraphStrategy())
    assert agent._graph_store is None


def test_agent_accepts_graph_store_keyword() -> None:
    store = InMemoryGraphStore()
    agent = Agent(strategy=_GraphStrategy(), graph_store=store)
    assert agent._graph_store is store


# ---- RuntimeContext exposure ----


@pytest.mark.asyncio
async def test_runtime_context_exposes_graph_store_when_present() -> None:
    """When the user passes `graph_store=`, the strategy receives it
    via `runtime.graph_store`."""
    store = InMemoryGraphStore()
    await store.add_node(GraphNode(id="paper:1", labels=("Doc",)))
    await store.add_node(GraphNode(id="paper:2", labels=("Doc",)))
    await store.add_edge(GraphEdge(src="paper:1", dst="paper:2", edge_type="CITES"))

    agent = Agent(
        model=FakeLLMClient(),
        strategy=_GraphStrategy(),
        graph_store=store,
    )
    result = await agent.run("paper:1")
    # Last step content should be paper:2 (one hop reachable).
    assert result.steps[-1].content == "paper:2"
    await agent.close()


@pytest.mark.asyncio
async def test_runtime_context_graph_store_none_when_unset() -> None:
    """Without a graph_store kwarg, strategies see `runtime.graph_store
    is None` and can fall back gracefully."""
    agent = Agent(model=FakeLLMClient(), strategy=_GraphStrategy())
    result = await agent.run("paper:1")
    assert result.steps[-1].content == "no graph_store"
    await agent.close()


# ---- Lifecycle ----


@pytest.mark.asyncio
async def test_agent_close_closes_graph_store() -> None:
    """`Agent.close()` must `await graph_store.close()` so external
    drivers (Neo4j / SurrealDB) release their connections."""
    closed_calls = []

    class _ProbeStore(InMemoryGraphStore):
        async def close(self) -> None:
            closed_calls.append(True)
            await super().close()

    store = _ProbeStore()
    agent = Agent(model=FakeLLMClient(), strategy=_GraphStrategy(), graph_store=store)
    await agent.close()
    assert closed_calls == [True]


@pytest.mark.asyncio
async def test_close_skips_graph_store_when_none() -> None:
    """No graph_store wired → close() doesn't trip on a None call."""
    agent = Agent(model=FakeLLMClient(), strategy=_GraphStrategy())
    await agent.close()  # must not raise
