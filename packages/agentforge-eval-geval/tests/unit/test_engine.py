"""Unit tests for `agentforge_eval_geval.engine.GEval`."""

from __future__ import annotations

import pytest
from agentforge._testing import FakeLLMClient
from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.values.messages import LLMResponse, TokenUsage
from agentforge_core.values.state import RunResult
from agentforge_eval_geval import GEval
from agentforge_eval_geval.graders import _RUBRICS_DIR


def _result(output: str = "the output") -> RunResult:
    return RunResult(
        output=output,
        cost_usd=0.0,
        tokens_in=0,
        tokens_out=0,
        run_id="01TEST",
        duration_ms=0,
    )


def _judge_response(content: str, *, cost: float = 0.001) -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=10, output_tokens=10),
        cost_usd=cost,
        model="judge-model",
        provider="fake",
    )


def _rubric() -> dict:
    return {
        "criteria": "Does the output address the task?",
        "scoring": "1.0 = yes, 0.0 = no",
    }


# --- construction --------------------------------------------------


def test_rubric_must_be_dict():
    judge = FakeLLMClient(responses=[])
    with pytest.raises(TypeError, match="rubric must be"):
        GEval(judge=judge, rubric="not a dict")  # type: ignore[arg-type]


def test_rubric_must_have_criteria():
    judge = FakeLLMClient(responses=[])
    with pytest.raises(ValueError, match="criteria"):
        GEval(judge=judge, rubric={"scoring": "x"})


def test_rubric_must_have_scoring():
    judge = FakeLLMClient(responses=[])
    with pytest.raises(ValueError, match="scoring"):
        GEval(judge=judge, rubric={"criteria": "x"})


# --- evaluate normal path ------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_parses_judge_json():
    judge = FakeLLMClient(
        responses=[_judge_response('{"score": 0.85, "reasoning": "addresses the task well"}')]
    )
    grader = GEval(judge=judge, rubric=_rubric())

    r = await grader.evaluate(_result(), {"task": "the task"})
    assert r.score == pytest.approx(0.85)
    assert r.label == "pass"
    assert "addresses the task" in (r.reasoning or "")


@pytest.mark.asyncio
async def test_evaluate_low_score_labels_fail():
    judge = FakeLLMClient(responses=[_judge_response('{"score": 0.2, "reasoning": "off-topic"}')])
    grader = GEval(judge=judge, rubric=_rubric())

    r = await grader.evaluate(_result(), {"task": "x"})
    assert r.score == pytest.approx(0.2)
    assert r.label == "fail"


@pytest.mark.asyncio
async def test_score_clamped_to_unit_interval():
    judge = FakeLLMClient(responses=[_judge_response('{"score": 1.7, "reasoning": "x"}')])
    grader = GEval(judge=judge, rubric=_rubric())
    r = await grader.evaluate(_result(), {"task": "t"})
    assert r.score == 1.0

    judge2 = FakeLLMClient(responses=[_judge_response('{"score": -0.5, "reasoning": "x"}')])
    grader2 = GEval(judge=judge2, rubric=_rubric())
    r2 = await grader2.evaluate(_result(), {"task": "t"})
    assert r2.score == 0.0


# --- defensive parsing ---------------------------------------------


@pytest.mark.asyncio
async def test_judge_returns_json_with_markdown_fences():
    """Judge wrapped its JSON in a ```json fence — engine should still
    extract the payload."""
    text = '```json\n{"score": 0.6, "reasoning": "ok"}\n```'
    judge = FakeLLMClient(responses=[_judge_response(text)])
    grader = GEval(judge=judge, rubric=_rubric())

    r = await grader.evaluate(_result(), {"task": "t"})
    assert r.score == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_judge_returns_no_json_falls_back_to_fail():
    judge = FakeLLMClient(responses=[_judge_response("I don't know how to score this.")])
    grader = GEval(judge=judge, rubric=_rubric())

    r = await grader.evaluate(_result(), {"task": "t"})
    assert r.score == 0.0
    assert "no JSON" in (r.reasoning or "")


@pytest.mark.asyncio
async def test_judge_returns_unparseable_json():
    judge = FakeLLMClient(responses=[_judge_response("{not valid json")])
    grader = GEval(judge=judge, rubric=_rubric())

    r = await grader.evaluate(_result(), {"task": "t"})
    assert r.score == 0.0


@pytest.mark.asyncio
async def test_judge_response_missing_score_field():
    judge = FakeLLMClient(responses=[_judge_response('{"reasoning": "no score here"}')])
    grader = GEval(judge=judge, rubric=_rubric())

    r = await grader.evaluate(_result(), {"task": "t"})
    assert r.score == 0.0


# --- judge failure -------------------------------------------------


@pytest.mark.asyncio
async def test_judge_call_failure_returns_fail_result():
    class BrokenJudge(FakeLLMClient):
        async def call(self, *args, **kwargs):
            raise RuntimeError("judge unreachable")

    grader = GEval(judge=BrokenJudge(), rubric=_rubric())
    r = await grader.evaluate(_result(), {"task": "t"})
    assert r.score == 0.0
    assert r.label == "fail"
    assert "RuntimeError" in (r.reasoning or "")


# --- budget integration --------------------------------------------


@pytest.mark.asyncio
async def test_judge_cost_commits_to_budget():
    judge = FakeLLMClient(
        responses=[_judge_response('{"score": 0.9, "reasoning": "x"}', cost=0.005)]
    )
    grader = GEval(judge=judge, rubric=_rubric())
    budget = BudgetPolicy(usd=1.0)

    await grader.evaluate(_result(), {"task": "t", "budget": budget})
    assert budget.spent_usd == pytest.approx(0.005)


@pytest.mark.asyncio
async def test_judge_cost_commit_over_cap_does_not_void_result():
    """If a judge call's cost would push over the cap, the EvalResult
    is still returned. Defensive — the score is informative."""
    judge = FakeLLMClient(
        responses=[_judge_response('{"score": 0.9, "reasoning": "x"}', cost=10.0)]
    )
    grader = GEval(judge=judge, rubric=_rubric())
    budget = BudgetPolicy(usd=0.01)

    r = await grader.evaluate(_result(), {"task": "t", "budget": budget})
    assert r.score == pytest.approx(0.9)


# --- rubric from YAML ----------------------------------------------


def test_from_rubric_file_missing_path(tmp_path):
    judge = FakeLLMClient(responses=[])
    with pytest.raises(FileNotFoundError):
        GEval.from_rubric_file(tmp_path / "no.yaml", judge=judge)


def test_from_rubric_file_loads_yaml(tmp_path):
    path = tmp_path / "my-rubric.yaml"
    path.write_text("criteria: judge the output\nscoring: 1.0 yes 0.0 no\n", encoding="utf-8")
    judge = FakeLLMClient(responses=[])
    grader = GEval.from_rubric_file(path, judge=judge)
    assert grader.name == "my-rubric"


def test_from_rubric_file_rejects_non_mapping(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- not a mapping\n", encoding="utf-8")
    judge = FakeLLMClient(responses=[])
    with pytest.raises(TypeError, match="mapping"):
        GEval.from_rubric_file(path, judge=judge)


# --- metadata ------------------------------------------------------


def test_default_cost_estimate():
    judge = FakeLLMClient(responses=[])
    grader = GEval(judge=judge, rubric=_rubric())
    assert grader.cost_estimate_usd == 0.01


def test_per_instance_cost_estimate_override():
    judge = FakeLLMClient(responses=[])
    grader = GEval(judge=judge, rubric=_rubric(), cost_estimate_usd=0.05)
    assert grader.cost_estimate_usd == 0.05


def test_per_instance_name_override():
    judge = FakeLLMClient(responses=[])
    grader = GEval(judge=judge, rubric=_rubric(), name="my-grader")
    assert grader.name == "my-grader"


# --- prompt construction --------------------------------------------


@pytest.mark.asyncio
async def test_inputs_injected_from_context():
    """Rubric `inputs: [expected]` causes `context['expected']` to be
    rendered into the user prompt."""
    judge = FakeLLMClient(responses=[_judge_response('{"score": 1.0, "reasoning": "match"}')])
    rubric = {
        "criteria": "judge",
        "scoring": "1.0 = match",
        "inputs": ["expected"],
    }
    grader = GEval(judge=judge, rubric=rubric)
    await grader.evaluate(_result("Paris"), {"task": "capital of France", "expected": "Paris"})

    assert len(judge.captured) == 1
    _, messages, _ = judge.captured[0]
    user = messages[0].content
    assert "expected" in user
    assert "Paris" in user


def test_rubrics_dir_exists():
    """The package ships its rubric YAML files; this is a smoke test
    that the files are packaged correctly."""
    assert _RUBRICS_DIR.is_dir()
    expected = {
        "correctness",
        "faithfulness",
        "groundedness",
        "hallucination",
        "relevance",
        "helpfulness",
    }
    shipped = {p.stem for p in _RUBRICS_DIR.glob("*.yaml")}
    assert expected <= shipped, f"missing rubrics: {expected - shipped}"
