"""Tests for `PresidioOutput` (feat-018 chunk 6)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from agentforge.testing import run_output_validator_conformance
from agentforge_guard_presidio import PresidioOutput
from agentforge_guard_presidio._runner import PresidioFinding


@dataclass
class PresidioFakeRunner:
    """Inline fake runner — lives in this module to avoid the
    workspace root conftest.py shadowing fixtures."""

    findings: list[PresidioFinding] = field(default_factory=list)
    received: list[str] = field(default_factory=list)

    async def analyze(
        self,
        text: str,
        entities: list[str],
        score_threshold: float,
    ) -> list[PresidioFinding]:
        self.received.append(text)
        return [
            f for f in self.findings if f.entity_type in entities and f.score >= score_threshold
        ]

    async def anonymize(
        self,
        text: str,
        findings: list[PresidioFinding],
    ) -> str:
        out = text
        for f in sorted(findings, key=lambda x: x.start, reverse=True):
            out = out[: f.start] + f"<{f.entity_type}>" + out[f.end :]
        return out


@pytest.mark.asyncio
async def test_presidio_passes_clean_output() -> None:
    fake = PresidioFakeRunner()
    v = PresidioOutput(runner=fake)
    result = await v.validate("The weather is nice today.", {})
    assert result.passed


@pytest.mark.asyncio
async def test_presidio_detects_and_redacts_email() -> None:
    fake = PresidioFakeRunner(
        findings=[
            PresidioFinding(entity_type="EMAIL_ADDRESS", start=13, end=30, score=0.95),
        ],
    )
    v = PresidioOutput(runner=fake)
    result = await v.validate("Email me at alice@example.com.", {})
    assert not result.passed
    assert "EMAIL_ADDRESS" in result.violations
    assert "<EMAIL_ADDRESS>" in result.redacted_content  # type: ignore[operator]


@pytest.mark.asyncio
async def test_presidio_score_only_action_no_redaction() -> None:
    fake = PresidioFakeRunner(
        findings=[
            PresidioFinding(entity_type="EMAIL_ADDRESS", start=0, end=5, score=0.9),
        ],
    )
    v = PresidioOutput(runner=fake, action="score-only")
    result = await v.validate("alice@example.com is here", {})
    assert not result.passed
    assert result.redacted_content is None


def test_presidio_rejects_unknown_action() -> None:
    with pytest.raises(ValueError, match="unknown action"):
        PresidioOutput(action="block")


class _ContentAwareFake:
    """Returns findings only when the text contains an `@`. Lets the
    conformance suite see a benign-pass + obvious-fail pair."""

    async def analyze(
        self,
        text: str,
        entities: list[str],
        score_threshold: float,
    ) -> list[PresidioFinding]:
        del entities, score_threshold
        if "@" in text:
            return [PresidioFinding(entity_type="EMAIL_ADDRESS", start=0, end=10, score=0.99)]
        return []

    async def anonymize(
        self,
        text: str,
        findings: list[PresidioFinding],
    ) -> str:
        del findings
        return text.replace("@", "<EMAIL_ADDRESS>")


@pytest.mark.asyncio
async def test_presidio_passes_conformance_suite() -> None:
    await run_output_validator_conformance(
        PresidioOutput(runner=_ContentAwareFake()),
        benign="this is fine",
        obvious_violation="alice@example.com is in this text",
    )
