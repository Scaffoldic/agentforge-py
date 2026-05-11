"""Tests for `agentforge eval` (feat-017 chunk 5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentforge.cli.main import main
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.resolver import register
from agentforge_core.values.state import AgentState, Step


class _OneStepStrategy(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="observe", content=state.task))
        return state


@pytest.fixture(autouse=True)
def _register_strategy() -> None:
    register("strategies", "noop-eval")(_OneStepStrategy)


def _write_cfg(tmp_path: Path) -> Path:
    cfg = tmp_path / "agentforge.yaml"
    cfg.write_text("agent:\n  strategy: noop-eval\n", encoding="utf-8")
    return cfg


def _write_fixtures(tmp_path: Path, fixtures: list[dict[str, str]]) -> Path:
    p = tmp_path / "fixtures.jsonl"
    p.write_text("\n".join(json.dumps(f) for f in fixtures), encoding="utf-8")
    return p


def test_eval_runs_all_fixtures(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _write_cfg(tmp_path)
    fixtures = _write_fixtures(tmp_path, [{"task": "a"}, {"task": "b"}, {"task": "c"}])
    code = main(
        [
            "eval",
            "--path",
            str(cfg),
            "--fixtures",
            str(fixtures),
            "--output-format",
            "json",
        ]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["fixtures"] == 3


def test_eval_threshold_fail_exits_5(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_cfg(tmp_path)
    fixtures = _write_fixtures(tmp_path, [{"task": "x"}])
    code = main(
        [
            "eval",
            "--path",
            str(cfg),
            "--fixtures",
            str(fixtures),
            "--threshold",
            "0.99",
            "--output-format",
            "json",
        ]
    )
    capsys.readouterr()
    # No evaluators registered → mean_score = 0.0 < 0.99 → fail.
    assert code == 5


def test_eval_junit_output_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _write_cfg(tmp_path)
    fixtures = _write_fixtures(tmp_path, [{"task": "x"}])
    code = main(
        [
            "eval",
            "--path",
            str(cfg),
            "--fixtures",
            str(fixtures),
            "--output-format",
            "junit",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "<testsuite" in out
    assert 'name="agentforge-eval"' in out
