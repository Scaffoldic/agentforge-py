"""Unit tests for the six named LLM-judge graders."""

from __future__ import annotations

import pytest
from agentforge._testing import FakeLLMClient
from agentforge_core.values.messages import LLMResponse, TokenUsage
from agentforge_core.values.state import RunResult
from agentforge_eval_geval import (
    Correctness,
    Faithfulness,
    Groundedness,
    Hallucination,
    Helpfulness,
    Relevance,
)


def _result(output: str = "the output") -> RunResult:
    return RunResult(
        output=output,
        cost_usd=0.0,
        tokens_in=0,
        tokens_out=0,
        run_id="01TEST",
        duration_ms=0,
    )


def _ok() -> LLMResponse:
    return LLMResponse(
        content='{"score": 0.8, "reasoning": "good"}',
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=10, output_tokens=10),
        cost_usd=0.001,
        model="judge",
        provider="fake",
    )


@pytest.mark.asyncio
async def test_correctness_dispatches_judge_and_injects_expected():
    judge = FakeLLMClient(responses=[_ok()])
    grader = Correctness(judge=judge)
    await grader.evaluate(_result("Paris"), {"task": "capital of France", "expected": "Paris"})
    _, messages, _ = judge.captured[0]
    user = messages[0].content
    assert "expected" in user
    assert "Paris" in user


@pytest.mark.asyncio
async def test_correctness_custom_ground_truth_field():
    judge = FakeLLMClient(responses=[_ok()])
    grader = Correctness(judge=judge, ground_truth_field="reference_answer")
    await grader.evaluate(_result("x"), {"task": "t", "reference_answer": "y"})
    _, messages, _ = judge.captured[0]
    user = messages[0].content
    assert "reference_answer" in user
    assert "y" in user


@pytest.mark.asyncio
async def test_faithfulness_dispatches_with_retrieved_docs():
    judge = FakeLLMClient(responses=[_ok()])
    grader = Faithfulness(judge=judge)
    await grader.evaluate(
        _result("Paris is the capital."),
        {"task": "capital of France", "retrieved_docs": "France's capital is Paris."},
    )
    _, messages, _ = judge.captured[0]
    user = messages[0].content
    assert "retrieved_docs" in user


@pytest.mark.asyncio
async def test_groundedness_uses_same_sources_field():
    judge = FakeLLMClient(responses=[_ok()])
    grader = Groundedness(judge=judge, sources_field="docs")
    await grader.evaluate(_result("x"), {"task": "t", "docs": "d"})
    _, messages, _ = judge.captured[0]
    user = messages[0].content
    assert "docs" in user


@pytest.mark.asyncio
async def test_hallucination_runs():
    judge = FakeLLMClient(responses=[_ok()])
    grader = Hallucination(judge=judge)
    r = await grader.evaluate(_result("x"), {"task": "t", "retrieved_docs": "d"})
    assert r.score == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_relevance_has_no_extra_inputs():
    judge = FakeLLMClient(responses=[_ok()])
    grader = Relevance(judge=judge)
    r = await grader.evaluate(_result("x"), {"task": "t"})
    assert r.score == pytest.approx(0.8)
    # Relevance rubric has no `inputs`; the user prompt should still
    # contain the task + output.
    _, messages, _ = judge.captured[0]
    user = messages[0].content
    assert "Task: t" in user
    assert "Output:" in user


@pytest.mark.asyncio
async def test_helpfulness_runs():
    judge = FakeLLMClient(responses=[_ok()])
    grader = Helpfulness(judge=judge)
    r = await grader.evaluate(_result("x"), {"task": "t"})
    assert r.score == pytest.approx(0.8)


def test_grader_names():
    judge = FakeLLMClient(responses=[])
    assert Correctness(judge=judge).name == "correctness"
    assert Faithfulness(judge=judge).name == "faithfulness"
    assert Groundedness(judge=judge).name == "groundedness"
    assert Hallucination(judge=judge).name == "hallucination"
    assert Relevance(judge=judge).name == "relevance"
    assert Helpfulness(judge=judge).name == "helpfulness"


def test_all_six_graders_have_default_cost():
    judge = FakeLLMClient(responses=[])
    for cls in (Correctness, Faithfulness, Groundedness, Hallucination, Relevance, Helpfulness):
        grader = cls(judge=judge)
        # default GEval cost_estimate is 0.01 — the named graders
        # inherit unless overridden.
        assert grader.cost_estimate_usd > 0
