"""Integration tests for `agentforge upgrade --notes` (enh-006 part 2).

Scaffolds a real agent, then drives the drift-report paths: the
report-only `--notes` query, the auto range, malformed input, and the
auto-summary printed at the end of a real upgrade.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import yaml
from agentforge.cli.new_cmd import _run_new
from agentforge.cli.upgrade_cmd import _run_upgrade


def _scaffold(tmp_path: Path) -> Path:
    dst = tmp_path / "agent"
    assert (
        _run_new(
            argparse.Namespace(
                project_slug="agent",
                template="minimal",
                provider="bedrock",
                no_prompts=True,
                dst=dst,
            )
        )
        == 0
    )
    return dst


def _set_pin(dst: Path, version: str) -> None:
    """Rewrite the recorded scaffold version (the drift report's 'from')."""
    path = dst / ".agentforge-state" / "answers.yml"
    answers = yaml.safe_load(path.read_text(encoding="utf-8"))
    answers["_template_version"] = version
    path.write_text(yaml.safe_dump(answers), encoding="utf-8")


def _upgrade_args(**kw: object) -> argparse.Namespace:
    base: dict[str, object] = {"to": None, "dry_run": False, "notes": None}
    base.update(kw)
    return argparse.Namespace(**base)


def test_notes_report_only_does_not_upgrade(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dst = _scaffold(tmp_path)
    capsys.readouterr()  # drop scaffold output

    rc = _run_upgrade(_upgrade_args(notes="0.2.4..0.3.0"), cwd=dst)

    assert rc == 0
    out = capsys.readouterr().out
    assert "drift from 0.2.4 → 0.3.0" in out
    assert "(closes #92)" in out  # enh-004 landed in 0.3.0
    assert "upgrade complete" not in out  # report-only — no upgrade ran


def test_notes_auto_range_uses_pin_and_installed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dst = _scaffold(tmp_path)
    _set_pin(dst, "0.2.4")
    capsys.readouterr()

    rc = _run_upgrade(_upgrade_args(notes="AUTO"), cwd=dst)

    assert rc == 0
    out = capsys.readouterr().out
    assert "drift from 0.2.4 →" in out  # from = the recorded pin


def test_notes_malformed_range_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dst = _scaffold(tmp_path)
    capsys.readouterr()

    rc = _run_upgrade(_upgrade_args(notes="not-a-range"), cwd=dst)

    assert rc == 1
    assert "Could not determine a version range" in capsys.readouterr().err


def test_notes_auto_without_recorded_pin_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dst = _scaffold(tmp_path)
    # Drop the recorded pin so AUTO can't resolve a "from".
    path = dst / ".agentforge-state" / "answers.yml"
    answers = yaml.safe_load(path.read_text(encoding="utf-8"))
    answers.pop("_template_version", None)
    path.write_text(yaml.safe_dump(answers), encoding="utf-8")
    capsys.readouterr()

    rc = _run_upgrade(_upgrade_args(notes="AUTO"), cwd=dst)

    assert rc == 1
    assert "Could not determine a version range" in capsys.readouterr().err


def test_auto_drift_summary_after_real_upgrade(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dst = _scaffold(tmp_path)
    _set_pin(dst, "0.2.4")  # pretend this agent was scaffolded under 0.2.4
    capsys.readouterr()

    rc = _run_upgrade(_upgrade_args(), cwd=dst)

    assert rc == 0
    out = capsys.readouterr().out
    assert "upgrade complete" in out  # the upgrade ran
    assert "drift from 0.2.4 →" in out  # and the drift summary followed
