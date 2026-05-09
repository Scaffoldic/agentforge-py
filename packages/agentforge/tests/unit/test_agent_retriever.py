"""Unit tests for `Agent`'s retriever integration (feat-007 chunk 4)."""

from __future__ import annotations

import math

import pytest
from agentforge import Agent, InMemoryStore, InMemoryVectorStore, Retriever
from agentforge._testing import FakeLLMClient
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge.strategies._base import get_runtime
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage
from agentforge_core.values.state import AgentState, Step


class _FakeEmbedder(EmbeddingClient):
    def __init__(self, *, dim: int = 4) -> None:
        self._dim = dim

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        if not texts:
            raise ValueError("empty")
        vectors = tuple(_text_to_vector(t, self._dim) for t in texts)
        return EmbeddingResponse(
            vectors=vectors,
            dimensions=self._dim,
            usage=TokenUsage(input_tokens=1, output_tokens=0),
            cost_usd=0.0,
            model="fake",
            provider="fake",
        )

    async def close(self) -> None: ...

    def dimensions(self) -> int:
        return self._dim


def _text_to_vector(text: str, dim: int) -> tuple[float, ...]:
    raw = [0.01] * dim
    for i, ch in enumerate(text):
        raw[i % dim] += ord(ch)
    norm = math.sqrt(sum(x * x for x in raw))
    return tuple(x / norm for x in raw)


class _RetrievalStrategy(ReasoningStrategy):
    """Test-only strategy that pulls one match from the retriever and
    surfaces it on the state's last step."""

    async def run(self, state: AgentState) -> AgentState:
        runtime = get_runtime(state)
        if runtime.retriever is None:
            state.steps.append(Step(iteration=0, kind="observe", content="no retriever"))
            return state
        matches = await runtime.retriever.retrieve(state.task, top_k=1)
        top = matches[0].text if matches else "(no match)"
        state.steps.append(Step(iteration=0, kind="observe", content=top))
        return state


# ---- Constructor wiring ----


def test_agent_without_retriever_keyword_defaults_to_none() -> None:
    """Existing callers that don't pass `retriever=` keep working."""
    agent = Agent(strategy=_RetrievalStrategy())
    assert agent._retriever is None


def test_agent_accepts_retriever_keyword() -> None:
    embedder = _FakeEmbedder(dim=4)
    store = InMemoryVectorStore(dimensions=4)
    retriever = Retriever(store=store, embedder=embedder)
    agent = Agent(strategy=_RetrievalStrategy(), retriever=retriever)
    assert agent._retriever is retriever


# ---- Runtime context plumbing ----


@pytest.mark.asyncio
async def test_strategy_sees_retriever_via_runtime_context() -> None:
    """End-to-end: Agent builds the RuntimeContext with the retriever
    we passed; the strategy reads it back via get_runtime(state)."""
    embedder = _FakeEmbedder(dim=4)
    store = InMemoryVectorStore(dimensions=4)
    retriever = Retriever(store=store, embedder=embedder)
    await retriever.add_documents(
        ["paris is the capital of france", "the louvre is in paris"],
        ids=["d1", "d2"],
    )

    fake_llm = FakeLLMClient(responses=[])
    async with Agent(
        model=fake_llm,
        strategy=_RetrievalStrategy(),
        retriever=retriever,
        install_log_filter=False,
    ) as agent:
        result = await agent.run("paris is the capital of france")

    assert result.output == "paris is the capital of france"


@pytest.mark.asyncio
async def test_strategy_sees_no_retriever_when_none_passed() -> None:
    """Without `retriever=`, the runtime context's retriever is None."""
    fake_llm = FakeLLMClient(responses=[])
    async with Agent(
        model=fake_llm,
        strategy=_RetrievalStrategy(),
        install_log_filter=False,
    ) as agent:
        result = await agent.run("anything")

    assert result.output == "no retriever"


# ---- Direct RuntimeContext shape ----


def test_runtime_context_carries_retriever_field() -> None:
    """Defensive check on the dataclass shape."""
    embedder = _FakeEmbedder(dim=4)
    store = InMemoryVectorStore(dimensions=4)
    retriever = Retriever(store=store, embedder=embedder)
    rt = RuntimeContext(
        llm=FakeLLMClient(responses=[]),
        tools=(),
        memory=InMemoryStore(),
        budget=BudgetPolicy(usd=1.0),
        retriever=retriever,
    )
    assert rt.retriever is retriever


def test_runtime_context_retriever_defaults_to_none() -> None:
    """Existing constructions that omit `retriever=` continue to work."""
    rt = RuntimeContext(
        llm=FakeLLMClient(responses=[]),
        tools=(),
        memory=InMemoryStore(),
        budget=BudgetPolicy(usd=1.0),
    )
    assert rt.retriever is None


# ---- Per-run fresh runtime ----


@pytest.mark.asyncio
async def test_retriever_persists_across_runs_of_same_agent() -> None:
    """Two `agent.run()` calls share the same retriever instance."""
    embedder = _FakeEmbedder(dim=4)
    store = InMemoryVectorStore(dimensions=4)
    retriever = Retriever(store=store, embedder=embedder)
    await retriever.add_documents(["alpha"], ids=["d1"])

    captured_retrievers: list[object] = []

    class _CaptureStrategy(ReasoningStrategy):
        async def run(self, state: AgentState) -> AgentState:
            captured_retrievers.append(state.metadata[RUNTIME_KEY].retriever)
            state.steps.append(Step(iteration=0, kind="observe", content="ok"))
            return state

    fake_llm = FakeLLMClient(responses=[])
    async with Agent(
        model=fake_llm,
        strategy=_CaptureStrategy(),
        retriever=retriever,
        install_log_filter=False,
    ) as agent:
        await agent.run("first")
        await agent.run("second")

    assert len(captured_retrievers) == 2
    assert captured_retrievers[0] is captured_retrievers[1]
    assert captured_retrievers[0] is retriever
