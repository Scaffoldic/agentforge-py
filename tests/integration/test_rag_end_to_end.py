"""Integration test — full RAG pipeline using only in-memory pieces.

Wires every layer of feat-007 together to prove the contracts compose:

    EmbeddingClient (fake)
        +
    InMemoryVectorStore
        =
    Retriever
        +
    Agent (with ReActLoop strategy)

A custom strategy uses `runtime.retriever` to ground its answer in
indexed documents. No live AWS, no Postgres, no network — just the
locked contracts and their reference implementations.
"""

from __future__ import annotations

import math

import pytest
from agentforge import Agent, InMemoryVectorStore, Retriever
from agentforge._testing import FakeLLMClient
from agentforge.strategies._base import get_runtime
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.messages import (
    EmbeddingResponse,
    LLMResponse,
    Message,
    TokenUsage,
)
from agentforge_core.values.state import AgentState, Step


class _FakeEmbedder(EmbeddingClient):
    """Deterministic text → vector for reproducible RAG tests."""

    def __init__(self, *, dim: int = 8) -> None:
        self._dim = dim

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        if not texts:
            raise ValueError("empty")
        vectors = tuple(_to_vec(t, self._dim) for t in texts)
        return EmbeddingResponse(
            vectors=vectors,
            dimensions=self._dim,
            usage=TokenUsage(input_tokens=sum(len(t) for t in texts), output_tokens=0),
            cost_usd=0.0,
            model="fake-embed",
            provider="fake",
        )

    async def close(self) -> None: ...

    def dimensions(self) -> int:
        return self._dim


def _to_vec(text: str, dim: int) -> tuple[float, ...]:
    """Stable text → vector via lowercased char-code accumulation."""
    raw = [0.01] * dim
    for i, ch in enumerate(text.lower()):
        raw[i % dim] += ord(ch)
    norm = math.sqrt(sum(x * x for x in raw))
    return tuple(x / norm for x in raw)


class _RagStrategy(ReasoningStrategy):
    """Minimal strategy that:
    1. Uses runtime.retriever to fetch the top match for the task.
    2. Emits an `observe` step containing the match text.
    3. Asks the LLM (a `FakeLLMClient`) for the final answer in one
       call, citing the retrieved context.
    """

    async def run(self, state: AgentState) -> AgentState:
        runtime = get_runtime(state)
        assert runtime.retriever is not None, "this test wires a retriever in"
        matches = await runtime.retriever.retrieve(state.task, top_k=1)
        context = matches[0].text if matches else "(no match)"
        state.steps.append(Step(iteration=0, kind="observe", content=f"retrieved: {context}"))

        # One LLM call to "synthesise" — fake it for the integration.
        response = await runtime.llm.call(
            system="answer using the retrieved context",
            messages=[
                Message(role="user", content=state.task),
                Message(role="assistant", content=f"Context:\n{context}"),
            ],
        )
        state.steps.append(
            Step(
                iteration=1,
                kind="synthesize",
                content=response.content,
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
                cost_usd=response.cost_usd,
            )
        )
        return state


@pytest.mark.asyncio
async def test_full_rag_pipeline_grounds_answer_in_retrieved_context() -> None:
    """End-to-end: index three docs, retrieve the most relevant for a
    user query, and pass it to a fake LLM that synthesises an answer.
    The answer surfaces in `result.output`."""

    embedder = _FakeEmbedder(dim=8)
    store = InMemoryVectorStore(dimensions=8)
    retriever = Retriever(store=store, embedder=embedder, top_k=2)
    await retriever.add_documents(
        [
            "the louvre is in paris france",
            "the eiffel tower is in paris france",
            "tokyo is the capital of japan",
        ],
        ids=["d1", "d2", "d3"],
    )

    # FakeLLMClient mimics a single synthesis call.
    fake_llm = FakeLLMClient(
        responses=[
            LLMResponse(
                content="The Louvre is in Paris.",
                stop_reason="end_turn",
                usage=TokenUsage(input_tokens=20, output_tokens=8),
                cost_usd=0.0001,
                model="fake",
                provider="fake",
            ),
        ]
    )

    async with Agent(
        model=fake_llm,
        strategy=_RagStrategy(),
        retriever=retriever,
        budget_usd=1.0,
        install_log_filter=False,
    ) as agent:
        result = await agent.run("Where is the Louvre?")

    assert result.output == "The Louvre is in Paris."
    assert result.finish_reason == "completed"

    # The trace shows both an observe (retrieved context) and a
    # synthesize step (the LLM's answer). The fake embedder isn't
    # semantic, so we don't assert *which* doc was retrieved — just
    # that the retrieval phase produced something and the synthesis
    # phase consumed it.
    kinds = [s.kind for s in result.steps]
    assert "observe" in kinds
    assert "synthesize" in kinds
    observe_step = next(s for s in result.steps if s.kind == "observe")
    assert str(observe_step.content).startswith("retrieved: ")
    # The fake LLM was called exactly once for the synthesis step.
    assert fake_llm.call_count == 1


@pytest.mark.asyncio
async def test_rag_pipeline_with_metadata_filter() -> None:
    """Same pipeline but the retriever filters by metadata so only
    `category=doc` items are eligible matches."""

    embedder = _FakeEmbedder(dim=8)
    store = InMemoryVectorStore(dimensions=8)
    retriever = Retriever(store=store, embedder=embedder, top_k=1)
    await retriever.add_documents(
        [
            "the louvre is in paris france",
            "internal note about paris",
        ],
        ids=["doc1", "note1"],
        metadata=[{"category": "doc"}, {"category": "note"}],
    )

    matches = await retriever.retrieve("where is the louvre", filter_metadata={"category": "doc"})
    assert len(matches) == 1
    assert matches[0].id == "doc1"
    assert matches[0].metadata["category"] == "doc"


@pytest.mark.asyncio
async def test_rag_with_in_memory_store_pieces_share_dimensions() -> None:
    """Constructor-time validation: store and embedder must agree on
    dimensions before the first call. Mismatch fails fast."""

    embedder = _FakeEmbedder(dim=8)
    store = InMemoryVectorStore(dimensions=4)  # deliberate mismatch
    with pytest.raises(ValueError, match="dimensions"):
        Retriever(store=store, embedder=embedder)
