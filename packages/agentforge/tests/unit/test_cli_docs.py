"""Tests for `agentforge docs` (feat-019 chunk 7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge.cli.main import main


def _seed_runbooks(tmp_path: Path) -> Path:
    runbooks = tmp_path / "docs" / "runbooks"
    runbooks.mkdir(parents=True)
    (runbooks / "01-set-up-new-agent.md").write_text("# 01 — Set up\n\nbody\n", encoding="utf-8")
    (runbooks / "02-add-a-tool.md").write_text("# 02 — Tool\n\nbody\n", encoding="utf-8")
    (runbooks / "16-configuration-reference.md").write_text(
        "# 16 — Config\n\nbody\n", encoding="utf-8"
    )
    return runbooks


def test_docs_list_prints_all_runbooks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runbooks = _seed_runbooks(tmp_path)
    code = main(["docs", "--path", str(runbooks)])
    out = capsys.readouterr().out
    assert code == 0
    assert "01-set-up-new-agent" in out
    assert "16-configuration-reference" in out


def test_docs_open_by_filename_stem_prints_content(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runbooks = _seed_runbooks(tmp_path)
    monkeypatch.delenv("EDITOR", raising=False)
    code = main(["docs", "02-add-a-tool", "--path", str(runbooks)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Tool" in out


def test_docs_open_by_bare_number(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runbooks = _seed_runbooks(tmp_path)
    monkeypatch.delenv("EDITOR", raising=False)
    code = main(["docs", "2", "--path", str(runbooks)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Tool" in out


def test_docs_open_by_alias(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runbooks = _seed_runbooks(tmp_path)
    monkeypatch.delenv("EDITOR", raising=False)
    code = main(["docs", "add-a-tool", "--path", str(runbooks)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Tool" in out


def test_docs_open_unknown_topic_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runbooks = _seed_runbooks(tmp_path)
    code = main(["docs", "nonsense", "--path", str(runbooks)])
    err = capsys.readouterr().err
    assert code == 1
    assert "no runbook matches" in err


def test_docs_missing_directory_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["docs", "--path", str(tmp_path / "no-runbooks")])
    err = capsys.readouterr().err
    assert code == 1
    assert "does not exist" in err


def test_docs_check_reports_no_drift_when_in_sync(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`docs check` against an empty bundle path reports no drift
    when the local dir is also empty."""
    from agentforge.cli import docs_cmd  # noqa: PLC0415

    bundled = tmp_path / "bundle"
    bundled.mkdir()
    monkeypatch.setattr(docs_cmd, "_bundled_runbooks_dir", lambda: bundled)
    local = tmp_path / "local"
    local.mkdir()
    code = main(["docs", "--check", "--path", str(local)])
    out = capsys.readouterr().out
    assert code == 0
    assert "in sync" in out


def test_docs_check_flags_drift_when_local_diverges(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agentforge.cli import docs_cmd  # noqa: PLC0415

    bundled = tmp_path / "bundle"
    bundled.mkdir()
    (bundled / "01-set-up-new-agent.md").write_text(
        "framework version of the runbook\n", encoding="utf-8"
    )
    monkeypatch.setattr(docs_cmd, "_bundled_runbooks_dir", lambda: bundled)
    local = tmp_path / "local"
    local.mkdir()
    (local / "01-set-up-new-agent.md").write_text("developer-edited version\n", encoding="utf-8")
    code = main(["docs", "--check", "--path", str(local)])
    out = capsys.readouterr().out
    assert code == 1
    assert "drift" in out


def test_docs_resolve_topic_with_md_suffix(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runbooks = _seed_runbooks(tmp_path)
    monkeypatch.delenv("EDITOR", raising=False)
    code = main(["docs", "02-add-a-tool.md", "--path", str(runbooks)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Tool" in out


def test_bundled_runbooks_dir_resolves() -> None:
    """The wheel ships `_shared/docs/runbooks/` after chunk 6."""
    from agentforge.cli.docs_cmd import _bundled_runbooks_dir  # noqa: PLC0415

    bundled = _bundled_runbooks_dir()
    assert bundled is not None
    assert (bundled / "01-set-up-new-agent.md.tmpl").exists() or (
        bundled / "01-set-up-new-agent.md"
    ).exists()
