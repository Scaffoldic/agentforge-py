"""Tests for `assert_snapshot` (feat-016 chunk 4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge_testing.snapshot import SnapshotMismatch, assert_snapshot


def test_first_run_creates_snapshot(tmp_path: Path) -> None:
    target = tmp_path / "snap.txt"
    assert_snapshot("hello world", target)
    assert target.read_text(encoding="utf-8") == "hello world"


def test_second_run_passes_when_match(tmp_path: Path) -> None:
    target = tmp_path / "snap.txt"
    target.write_text("hello", encoding="utf-8")
    assert_snapshot("hello", target)  # no raise


def test_mismatch_raises_with_diff(tmp_path: Path) -> None:
    target = tmp_path / "snap.txt"
    target.write_text("hello", encoding="utf-8")
    with pytest.raises(SnapshotMismatch, match="snapshot mismatch"):
        assert_snapshot("world", target)


def test_update_env_overwrites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "snap.txt"
    target.write_text("old", encoding="utf-8")
    monkeypatch.setenv("UPDATE_SNAPSHOTS", "1")
    assert_snapshot("new", target)
    assert target.read_text(encoding="utf-8") == "new"
