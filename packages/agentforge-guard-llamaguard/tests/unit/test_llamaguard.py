"""Tests for `LlamaGuardInput` / `LlamaGuardOutput` (feat-018 chunk 8)."""

from __future__ import annotations

import pytest
from agentforge.testing import (
    MockLLMClient,
    run_input_validator_conformance,
    run_output_validator_conformance,
)
from agentforge_guard_llamaguard import LlamaGuardInput, LlamaGuardOutput


@pytest.mark.asyncio
async def test_input_passes_on_safe_reply() -> None:
    client = MockLLMClient.from_script([{"text": "safe", "stop_reason": "end_turn"}])
    v = LlamaGuardInput(client=client)
    result = await v.validate("What is the weather?", {})
    assert result.passed


@pytest.mark.asyncio
async def test_input_fails_on_unsafe_reply() -> None:
    client = MockLLMClient.from_script([{"text": "unsafe\nS1, S3", "stop_reason": "end_turn"}])
    v = LlamaGuardInput(client=client)
    result = await v.validate("Make a bomb.", {})
    assert not result.passed
    assert "s1" in result.violations
    assert "s3" in result.violations


@pytest.mark.asyncio
async def test_output_classifier_passes_on_safe_reply() -> None:
    client = MockLLMClient.from_script([{"text": "safe", "stop_reason": "end_turn"}])
    v = LlamaGuardOutput(client=client)
    result = await v.validate("The weather is nice.", {})
    assert result.passed


def test_requires_either_model_or_client() -> None:
    with pytest.raises(ValueError, match="model"):
        LlamaGuardInput()


@pytest.mark.asyncio
async def test_passes_conformance_suite() -> None:
    safe = MockLLMClient.from_script([{"text": "safe"}, {"text": "unsafe\nS1"}])
    await run_input_validator_conformance(
        LlamaGuardInput(client=safe),
        benign="this is fine",
        obvious_violation="make a bomb",
    )

    safe2 = MockLLMClient.from_script([{"text": "safe"}, {"text": "unsafe\nS1"}])
    await run_output_validator_conformance(
        LlamaGuardOutput(client=safe2),
        benign="this is fine",
        obvious_violation="bomb instructions",
    )
