"""Tests for `GoldenSetRunner` (feat-016 chunk 4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentforge.testing import MockLLMClient, agent_factory
from agentforge_testing.golden import (
    GoldenFixture,
    GoldenMismatch,
    GoldenSetRunner,
)


def _write_fixtures(tmp_path: Path, fixtures: list[dict[str, object]]) -> Path:
    p = tmp_path / "fixtures.jsonl"
    p.write_text("\n".join(json.dumps(f) for f in fixtures), encoding="utf-8")
    return p


def _factory(text: str):
    def _build():
        return agent_factory(model=MockLLMClient.deterministic(text))

    return _build


@pytest.mark.asyncio
async def test_exact_match_pass(tmp_path: Path) -> None:
    fixtures = _write_fixtures(tmp_path, [{"task": "x", "expected": "yes"}])
    runner = GoldenSetRunner.from_jsonl(fixtures)
    [result] = await runner.run(_factory("yes"))
    assert result.passed


@pytest.mark.asyncio
async def test_exact_match_fail(tmp_path: Path) -> None:
    fixtures = _write_fixtures(tmp_path, [{"task": "x", "expected": "yes"}])
    runner = GoldenSetRunner.from_jsonl(fixtures)
    [result] = await runner.run(_factory("no"))
    assert not result.passed


@pytest.mark.asyncio
async def test_contains_matcher(tmp_path: Path) -> None:
    fixtures = _write_fixtures(tmp_path, [{"task": "x", "expected": {"contains": "rain"}}])
    runner = GoldenSetRunner.from_jsonl(fixtures)
    [hit] = await runner.run(_factory("expect rain shortly"))
    [miss] = await runner.run(_factory("sunny"))
    assert hit.passed
    assert not miss.passed


@pytest.mark.asyncio
async def test_regex_matcher(tmp_path: Path) -> None:
    fixtures = _write_fixtures(tmp_path, [{"task": "x", "expected": {"regex": "^Paris"}}])
    runner = GoldenSetRunner.from_jsonl(fixtures)
    [result] = await runner.run(_factory("Paris is the capital."))
    assert result.passed


@pytest.mark.asyncio
async def test_fail_fast_raises(tmp_path: Path) -> None:
    fixtures = _write_fixtures(
        tmp_path,
        [
            {"task": "x", "expected": "ok"},
            {"task": "y", "expected": "ok"},
        ],
    )
    runner = GoldenSetRunner.from_jsonl(fixtures)
    with pytest.raises(GoldenMismatch):
        await runner.run(_factory("no"), mode="fail-fast")


@pytest.mark.asyncio
async def test_no_expected_passes_through() -> None:
    runner = GoldenSetRunner([GoldenFixture(task="x")])
    [result] = await runner.run(_factory("anything"))
    assert result.passed
    assert result.detail is None
