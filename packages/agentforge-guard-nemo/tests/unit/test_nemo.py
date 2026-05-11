"""Tests for `NemoInput` / `NemoOutput` (feat-018 chunk 7)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from agentforge.testing import (
    run_input_validator_conformance,
    run_output_validator_conformance,
)
from agentforge_guard_nemo import NemoInput, NemoOutput
from agentforge_guard_nemo._runner import RailResult


@dataclass
class NemoFakeRunner:
    """Inline fake NemoRunner — lives here to avoid the workspace
    root conftest.py shadowing fixtures."""

    input_result: RailResult = field(default_factory=lambda: RailResult(allowed=True))
    output_result: RailResult = field(default_factory=lambda: RailResult(allowed=True))

    async def check_input(self, content: str) -> RailResult:
        del content
        return self.input_result

    async def check_output(self, content: str) -> RailResult:
        del content
        return self.output_result


@pytest.mark.asyncio
async def test_nemo_input_passes_when_rail_allows() -> None:
    v = NemoInput(runner=NemoFakeRunner())
    result = await v.validate("anything", {})
    assert result.passed


@pytest.mark.asyncio
async def test_nemo_input_fails_when_rail_blocks() -> None:
    runner = NemoFakeRunner(
        input_result=RailResult(allowed=False, rationale="refused due to policy")
    )
    v = NemoInput(runner=runner)
    result = await v.validate("anything", {})
    assert not result.passed
    assert "nemo_input_rail" in result.violations
    assert result.metadata["rationale"] == "refused due to policy"


@pytest.mark.asyncio
async def test_nemo_output_passes_when_rail_allows() -> None:
    v = NemoOutput(runner=NemoFakeRunner())
    result = await v.validate("anything", {})
    assert result.passed


def test_nemo_requires_either_config_or_runner() -> None:
    with pytest.raises(ValueError, match="config_path"):
        NemoInput()


@pytest.mark.asyncio
async def test_nemo_passes_conformance() -> None:
    benign_runner = NemoFakeRunner()
    block_runner = NemoFakeRunner(
        input_result=RailResult(allowed=False, rationale="blocked"),
        output_result=RailResult(allowed=False, rationale="blocked"),
    )

    class _ContentAware:
        async def check_input(self, content: str) -> RailResult:
            return RailResult(allowed="bad" not in content, rationale="content-aware")

        async def check_output(self, content: str) -> RailResult:
            return RailResult(allowed="bad" not in content, rationale="content-aware")

    await run_input_validator_conformance(
        NemoInput(runner=_ContentAware()),
        benign="this is fine",
        obvious_violation="this is bad",
    )
    await run_output_validator_conformance(
        NemoOutput(runner=_ContentAware()),
        benign="this is fine",
        obvious_violation="this is bad",
    )
    del benign_runner, block_runner  # silence unused
