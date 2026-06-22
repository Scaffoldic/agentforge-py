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

    result = _shared_scaffold.inject_shared_scaffold(
        dst, template_name="minimal", template_version="0.0.1"
    )
    assert len(result.written) == 1
    content = (dst / "RAW.txt").read_text(encoding="utf-8")
    assert "hello world" in content


def test_injection_renders_tmpl_through_jinja(stub_shared_dir: Path, tmp_path: Path) -> None:
    (stub_shared_dir / "README.md.tmpl").write_text(
        "# {{ project_name }}\n\nslug: {{ project_slug }}\n",
        encoding="utf-8",
    )
    dst = _write_destination(tmp_path)

    result = _shared_scaffold.inject_shared_scaffold(
        dst, template_name="minimal", template_version="0.0.1"
    )
    assert len(result.written) == 1
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
    result = _shared_scaffold.inject_shared_scaffold(
        dst, template_name="minimal", template_version="0.0.1"
    )
    assert result.written == []


# ----------------------------------------------------------------------
# bug-025: re-injection must respect fork status + custom blocks
# ----------------------------------------------------------------------


def test_reinjection_skips_forked_file(stub_shared_dir: Path, tmp_path: Path) -> None:
    """A file the lock marks `forked` is never rewritten and its lock
    entry is left untouched."""
    from agentforge.cli._scaffold_state import read_lock, write_lock  # noqa: PLC0415

    (stub_shared_dir / "AGENTS.md").write_text("# template v2 rules\n", encoding="utf-8")
    dst = _write_destination(tmp_path)
    # Consumer forked AGENTS.md and hand-wrote it.
    (dst / "AGENTS.md").write_text("# MY forked rules — do not touch\n", encoding="utf-8")
    write_lock(
        dst,
        {"AGENTS.md": {"hash": "x", "source_module": "s", "source_version": "0", "forked": True}},
    )

    result = _shared_scaffold.inject_shared_scaffold(
        dst, template_name="minimal", template_version="0.0.2"
    )

    assert "AGENTS.md" in result.skipped_forked
    assert "AGENTS.md" not in result.written
    # File and lock entry both preserved verbatim.
    assert (dst / "AGENTS.md").read_text(encoding="utf-8") == "# MY forked rules — do not touch\n"
    assert read_lock(dst)["AGENTS.md"]["forked"] is True


def test_reinjection_preserves_custom_block(stub_shared_dir: Path, tmp_path: Path) -> None:
    """The developer-owned `agentforge:custom` tail survives while the
    managed region is refreshed from the template."""
    end = "<!-- agentforge:end-managed -->"
    start = "<!-- agentforge:custom -->"
    custom_end = "<!-- agentforge:end-custom -->"

    (stub_shared_dir / "AGENTS.md").write_text(
        f"# Rules v2\n\nrefreshed managed body\n\n{end}\n\n"
        f"{start}\nTEMPLATE default custom\n{custom_end}\n",
        encoding="utf-8",
    )
    dst = _write_destination(tmp_path)
    # Existing on-disk file: old managed region + the consumer's edits
    # inside the custom block.
    (dst / "AGENTS.md").write_text(
        f"# AGENTFORGE-MANAGED: x\n# Rules v1\n\nold managed body\n\n{end}\n\n"
        f"{start}\nOUR team notes — keep me\n{custom_end}\n",
        encoding="utf-8",
    )

    result = _shared_scaffold.inject_shared_scaffold(
        dst, template_name="minimal", template_version="0.0.2"
    )

    out = (dst / "AGENTS.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in result.preserved_custom
    assert "refreshed managed body" in out  # managed region updated
    assert "OUR team notes — keep me" in out  # consumer custom preserved
    assert "TEMPLATE default custom" not in out  # template default NOT forced back
    assert "old managed body" not in out


def test_reinjection_dry_run_writes_nothing(stub_shared_dir: Path, tmp_path: Path) -> None:
    """`dry_run` classifies every file but touches neither disk nor lock."""
    from agentforge.cli._scaffold_state import read_lock  # noqa: PLC0415

    (stub_shared_dir / "RAW.txt").write_text("template content\n", encoding="utf-8")
    dst = _write_destination(tmp_path)

    result = _shared_scaffold.inject_shared_scaffold(
        dst, template_name="minimal", template_version="0.0.1", dry_run=True
    )

    assert result.written == ["RAW.txt"]
    assert not (dst / "RAW.txt").exists()
    assert read_lock(dst) == {}
