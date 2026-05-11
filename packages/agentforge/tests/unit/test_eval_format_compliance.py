"""Unit tests for `agentforge.eval.format_compliance` (feat-006 chunk 3)."""

from __future__ import annotations

import pytest
from agentforge.eval import FormatCompliance
from agentforge_core.values.state import RunResult
from pydantic import BaseModel


def _result(output):
    return RunResult(
        output=output,
        cost_usd=0.0,
        tokens_in=0,
        tokens_out=0,
        run_id="01TEST",
        duration_ms=0,
    )


# --- construction validation -----------------------------------------


def test_no_mode_set_rejected():
    with pytest.raises(ValueError, match="exactly one"):
        FormatCompliance()


def test_multiple_modes_set_rejected():
    with pytest.raises(ValueError, match="exactly one"):
        FormatCompliance(regex=r"^\d+$", json_parseable=True)


# --- regex mode ------------------------------------------------------


@pytest.mark.asyncio
async def test_regex_match_passes():
    grader = FormatCompliance(regex=r"^[A-Z]{3}-\d{4}$")
    r = await grader.evaluate(_result("ABC-1234"), {})
    assert r.score == 1.0
    assert r.label == "pass"


@pytest.mark.asyncio
async def test_regex_no_match_fails():
    grader = FormatCompliance(regex=r"^[A-Z]{3}-\d{4}$")
    r = await grader.evaluate(_result("invalid-format"), {})
    assert r.score == 0.0
    assert r.label == "fail"


@pytest.mark.asyncio
async def test_regex_partial_match_fails_fullmatch_semantics():
    """We use `fullmatch` — substring matches don't count."""
    grader = FormatCompliance(regex=r"\d+")
    r = await grader.evaluate(_result("the number is 42"), {})
    assert r.score == 0.0


@pytest.mark.asyncio
async def test_regex_non_string_output_fails_cleanly():
    grader = FormatCompliance(regex=r".*")
    r = await grader.evaluate(_result({"key": "value"}), {})
    assert r.score == 0.0
    assert "string output" in (r.reasoning or "")


# --- pydantic model mode --------------------------------------------


class _Answer(BaseModel):
    answer: str
    confidence: float


@pytest.mark.asyncio
async def test_pydantic_dict_output_validates():
    grader = FormatCompliance(pydantic_model=_Answer)
    r = await grader.evaluate(_result({"answer": "yes", "confidence": 0.9}), {})
    assert r.score == 1.0
    assert r.label == "pass"


@pytest.mark.asyncio
async def test_pydantic_json_string_output_validates():
    grader = FormatCompliance(pydantic_model=_Answer)
    r = await grader.evaluate(_result('{"answer": "yes", "confidence": 0.9}'), {})
    assert r.score == 1.0


@pytest.mark.asyncio
async def test_pydantic_missing_field_fails():
    grader = FormatCompliance(pydantic_model=_Answer)
    r = await grader.evaluate(_result({"answer": "yes"}), {})  # missing confidence
    assert r.score == 0.0
    assert "validation failed" in (r.reasoning or "")


@pytest.mark.asyncio
async def test_pydantic_wrong_type_fails():
    grader = FormatCompliance(pydantic_model=_Answer)
    r = await grader.evaluate(_result({"answer": "yes", "confidence": "high"}), {})
    assert r.score == 0.0


@pytest.mark.asyncio
async def test_pydantic_unparseable_json_string_fails():
    grader = FormatCompliance(pydantic_model=_Answer)
    r = await grader.evaluate(_result("not json"), {})
    assert r.score == 0.0
    assert "JSON-parseable" in (r.reasoning or "")


# --- json_parseable mode --------------------------------------------


@pytest.mark.asyncio
async def test_json_parseable_dict_passes_directly():
    grader = FormatCompliance(json_parseable=True)
    r = await grader.evaluate(_result({"any": "dict"}), {})
    assert r.score == 1.0


@pytest.mark.asyncio
async def test_json_parseable_string_passes():
    grader = FormatCompliance(json_parseable=True)
    r = await grader.evaluate(_result('{"valid": true}'), {})
    assert r.score == 1.0


@pytest.mark.asyncio
async def test_json_parseable_invalid_string_fails():
    grader = FormatCompliance(json_parseable=True)
    r = await grader.evaluate(_result("not { json"), {})
    assert r.score == 0.0


@pytest.mark.asyncio
async def test_metadata_declares_zero_cost():
    grader = FormatCompliance(regex=".*")
    assert grader.cost_estimate_usd == 0.0
    assert grader.name == "format_compliance"
