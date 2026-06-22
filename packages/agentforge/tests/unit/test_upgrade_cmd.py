"""End-to-end tests for `agentforge upgrade` (bug-025).

The data-loss bug: `agentforge upgrade` re-injected the shared
scaffold (AGENTS.md / CLAUDE.md / runbooks) wholesale, ignoring fork
status and erasing the developer-owned ``agentforge:custom`` block
these files promise will "survive upgrade". These tests scaffold a
real agent with `agentforge new`, mutate it the way a consumer would,
then run `agentforge upgrade` and assert nothing is clobbered.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from agentforge.cli.new_cmd import _run_new
from agentforge.cli.upgrade_cmd import _run_fork, _run_upgrade

CUSTOM_START = "<!-- agentforge:custom -->"
CUSTOM_END = "<!-- agentforge:end-custom -->"
SENTINEL = "OUR-TEAM-CUSTOM-NOTE — must survive upgrade"


def _scaffold(tmp_path: Path) -> Path:
    dst = tmp_path / "agent"
    code = _run_new(
        argparse.Namespace(
            project_slug="agent",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    assert code == 0
    return dst


def _put_custom_note(path: Path, note: str) -> None:
    """Drop a sentinel line inside the file's custom block."""
    text = path.read_text(encoding="utf-8")
    assert CUSTOM_START in text, f"{path} is not a three-section file"
    head, _, tail = text.partition(CUSTOM_START)
    path.write_text(f"{head}{CUSTOM_START}\n{note}\n{tail.split(CUSTOM_START, 1)[-1]}", "utf-8")


def test_upgrade_preserves_custom_block_in_shared_file(tmp_path: Path) -> None:
    dst = _scaffold(tmp_path)
    agents_md = dst / "AGENTS.md"
    _put_custom_note(agents_md, SENTINEL)

    code = _run_upgrade(argparse.Namespace(to=None, dry_run=False, notes=None), cwd=dst)

    assert code == 0
    out = agents_md.read_text(encoding="utf-8")
    assert SENTINEL in out, "custom block erased by upgrade (bug-025)"
    # Managed region is still there (file wasn't truncated to just custom).
    assert "agentforge:end-managed" in out


def test_upgrade_skips_forked_file(tmp_path: Path) -> None:
    dst = _scaffold(tmp_path)
    runbook = dst / "docs" / "runbooks" / "02-add-a-tool.md"
    assert runbook.exists()
    # Fork it, then hand-rewrite it entirely.
    assert _run_fork(argparse.Namespace(path="docs/runbooks/02-add-a-tool.md"), cwd=dst) == 0
    runbook.write_text("# Completely my own runbook now\n", encoding="utf-8")

    code = _run_upgrade(argparse.Namespace(to=None, dry_run=False, notes=None), cwd=dst)

    assert code == 0
    assert runbook.read_text(encoding="utf-8") == "# Completely my own runbook now\n"


def test_upgrade_dry_run_writes_nothing_and_lists_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dst = _scaffold(tmp_path)
    agents_md = dst / "AGENTS.md"
    _put_custom_note(agents_md, SENTINEL)
    before = agents_md.read_text(encoding="utf-8")

    code = _run_upgrade(argparse.Namespace(to=None, dry_run=True, notes=None), cwd=dst)

    assert code == 0
    # Nothing written.
    assert agents_md.read_text(encoding="utf-8") == before
    out = capsys.readouterr().out
    assert "dry-run" in out
    # Per-file plan, not just a one-line summary (issue #114 ask 3).
    assert "AGENTS.md" in out
    assert "preserve custom block" in out
