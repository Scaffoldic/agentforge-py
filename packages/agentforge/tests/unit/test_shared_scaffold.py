"""Tests for `inject_shared_scaffold` (feat-019 chunk 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge.cli import _shared_scaffold


@pytest.fixture
def stub_shared_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Override `_shared_root()` to point at a tmp directory so we
    control the shared payload without touching the wheel-bundled
    `_shared/` dir."""
    shared_dir = tmp_path / "stub-shared"
    shared_dir.mkdir()
    monkeypatch.setattr(_shared_scaffold, "_shared_root", lambda: shared_dir)
    return shared_dir


def _write_destination(tmp_path: Path) -> Path:
    dst = tmp_path / "dst"
    dst.mkdir()
    state_dir = dst / ".agentforge-state"
    state_dir.mkdir()
    (state_dir / "answers.yml").write_text(
        "project_slug: stub-agent\nproject_name: Stub Agent\nllm_provider: bedrock\n",
        encoding="utf-8",
    )
    (state_dir / "managed-files.lock").write_text("", encoding="utf-8")
    return dst


def test_injection_copies_verbatim_files(stub_shared_dir: Path, tmp_path: Path) -> None:
    (stub_shared_dir / "RAW.txt").write_text("hello world", encoding="utf-8")
    dst = _write_destination(tmp_path)

    count = _shared_scaffold.inject_shared_scaffold(
        dst, template_name="minimal", template_version="0.0.1"
    )
    assert count == 1
    content = (dst / "RAW.txt").read_text(encoding="utf-8")
    assert "hello world" in content


def test_injection_renders_tmpl_through_jinja(stub_shared_dir: Path, tmp_path: Path) -> None:
    (stub_shared_dir / "README.md.tmpl").write_text(
        "# {{ project_name }}\n\nslug: {{ project_slug }}\n",
        encoding="utf-8",
    )
    dst = _write_destination(tmp_path)

    count = _shared_scaffold.inject_shared_scaffold(
        dst, template_name="minimal", template_version="0.0.1"
    )
    assert count == 1
    content = (dst / "README.md").read_text(encoding="utf-8")
    assert "# Stub Agent" in content
    assert "slug: stub-agent" in content


def test_injection_prepends_marker_for_known_suffix(stub_shared_dir: Path, tmp_path: Path) -> None:
    (stub_shared_dir / "config.yaml").write_text("key: value\n", encoding="utf-8")
    dst = _write_destination(tmp_path)

    _shared_scaffold.inject_shared_scaffold(dst, template_name="minimal", template_version="0.0.1")
    content = (dst / "config.yaml").read_text(encoding="utf-8")
    assert content.splitlines()[0].startswith("# AGENTFORGE-MANAGED:")


def test_injection_extends_lock_with_shared_entries(stub_shared_dir: Path, tmp_path: Path) -> None:
    from agentforge.cli._scaffold_state import read_lock  # noqa: PLC0415

    (stub_shared_dir / "AGENTS.md").write_text("# AI rules\n", encoding="utf-8")
    dst = _write_destination(tmp_path)

    _shared_scaffold.inject_shared_scaffold(dst, template_name="minimal", template_version="0.0.1")
    lock = read_lock(dst)
    assert "AGENTS.md" in lock
    assert lock["AGENTS.md"]["source_module"] == "template:minimal:_shared"


def test_injection_returns_zero_when_shared_root_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(_shared_scaffold, "_shared_root", lambda: None)
    dst = _write_destination(tmp_path)
    count = _shared_scaffold.inject_shared_scaffold(
        dst, template_name="minimal", template_version="0.0.1"
    )
    assert count == 0
