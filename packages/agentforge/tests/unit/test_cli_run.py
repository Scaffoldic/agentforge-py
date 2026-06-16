"""Tests for `agentforge run` (feat-017 chunk 4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentforge.cli.main import main
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.resolver import register
from agentforge_core.values.state import AgentState, Step


class _NoOpStrategy(ReasoningStrategy):
    """Single-step strategy returning the task as the output."""

    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="observe", content=state.task))
        return state


@pytest.fixture(autouse=True)
def _register_strategy() -> None:
    register("strategies", "noop-run")(_NoOpStrategy)


def _write_yaml(tmp_path: Path) -> Path:
    cfg = tmp_path / "agentforge.yaml"
    cfg.write_text(
        "agent:\n  strategy: noop-run\n  budget:\n    usd: 5\n",
        encoding="utf-8",
    )
    return cfg


def test_run_plain_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _write_yaml(tmp_path)
    code = main(["run", "--path", str(cfg), "--output-format", "plain", "hello world"])
    out = capsys.readouterr().out.strip()
    assert code == 0
    assert out == "hello world"


def test_run_json_output_has_expected_fields(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_yaml(tmp_path)
    code = main(["run", "--path", str(cfg), "--output-format", "json", "hi"])
    out = capsys.readouterr().out
    assert code == 0
    payload = json.loads(out)
    for field in ("output", "run_id", "cost_usd", "tokens_in", "tokens_out", "steps"):
        assert field in payload


def test_run_task_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _write_yaml(tmp_path)
    task = tmp_path / "task.txt"
    task.write_text("from-file", encoding="utf-8")
    code = main(["run", "--path", str(cfg), "--task-file", str(task), "--output-format", "plain"])
    assert capsys.readouterr().out.strip() == "from-file"
    assert code == 0


def test_run_override_applied(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _write_yaml(tmp_path)
    code = main(
        [
            "run",
            "--path",
            str(cfg),
            "--override",
            "agent.budget.usd=2.5",
            "--output-format",
            "plain",
            "x",
        ]
    )
    assert code == 0


def test_run_missing_task_returns_generic_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_yaml(tmp_path)
    code = main(["run", "--path", str(cfg)])
    err = capsys.readouterr().err
    assert code == 1
    assert "must provide a task" in err


def test_run_replay_without_memory_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_yaml(tmp_path)
    code = main(["run", "--path", str(cfg), "--replay", "some-run", "x"])
    err = capsys.readouterr().err
    assert code == 1
    assert "modules.memory" in err


def _write_yaml_with_memory(tmp_path: Path) -> Path:
    """Config with sqlite memory so `--record` / `--replay` have a store."""
    db = tmp_path / "rec.sqlite"
    cfg = tmp_path / "agentforge.yaml"
    cfg.write_text(
        "agent:\n"
        "  strategy: noop-run\n"
        "  budget:\n    usd: 5\n"
        "modules:\n"
        "  memory:\n"
        "    driver: sqlite\n"
        f"    config:\n      path: {db}\n",
        encoding="utf-8",
    )
    return cfg


def test_run_replay_happy_path_reconstructs_agent_with_strategy(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Regression for bug-023: replaying a recorded run must succeed.

    The replay path rebuilds the Agent and re-drives the recorded loop,
    so it needs the configured strategy. Previously it constructed
    `Agent(model=replay_llm, memory=memory)` with no strategy, so this
    failed with "No reasoning strategy provided" (exit 1) for every
    real recording — the happy path had no test.
    """
    pytest.importorskip("agentforge_memory_sqlite")
    cfg = _write_yaml_with_memory(tmp_path)

    # Record a run.
    code = main(["run", "--path", str(cfg), "--record", "--output-format", "json", "hello"])
    assert code == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    # Replay it — must reconstruct the agent (with strategy) and exit 0.
    code = main(
        ["run", "--path", str(cfg), "--replay", run_id, "--output-format", "plain", "hello"]
    )
    out = capsys.readouterr().out.strip()
    assert code == 0, out
    assert out == "hello"


def test_run_invalid_config_returns_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = tmp_path / "agentforge.yaml"
    cfg.write_text("agent:\n  budget:\n    usd: -1\n", encoding="utf-8")
    code = main(["run", "--path", str(cfg), "x"])
    err = capsys.readouterr().err
    assert code == 2, err
