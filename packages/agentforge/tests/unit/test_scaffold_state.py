"""Unit tests for `_scaffold_state` + fork/unfork/status (feat-011 chunks 3+5).

`agentforge upgrade` against a real Copier-rendered scaffold +
template-version step is covered separately; here we focus on the
lock-file + marker-header + fork-flow primitives.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from agentforge.cli._scaffold_state import (
    file_status,
    hash_content,
    lock_path,
    marker_for,
    prepend_markers,
    read_lock,
    strip_marker,
    write_managed_files_lock,
)
from agentforge.cli.new_cmd import _run_new
from agentforge.cli.upgrade_cmd import (
    _run_fork,
    _run_status,
    _run_unfork,
    _run_upgrade,
)

# --- marker_for picks comment style per file ext ----------------


def test_marker_for_python_uses_hash_comment():
    m = marker_for(".py", "template:minimal", "0.0.1", "abc123")
    assert m == "# AGENTFORGE-MANAGED: template:minimal@0.0.1 hash:abc123"


def test_marker_for_html_uses_xml_comment():
    m = marker_for(".html", "template:minimal", "0.0.1", "abc123")
    assert m.startswith("<!--")
    assert m.endswith("-->")


def test_marker_for_unknown_ext_returns_none():
    assert marker_for(".bin", "template:minimal", "0.0.1", "abc") is None


# --- write_managed_files_lock + prepend_markers ------------------


def test_lock_captures_every_file(tmp_path: Path):
    (tmp_path / "a.py").write_text("print('a')\n")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "b.py").write_text("print('b')\n")

    lock = write_managed_files_lock(tmp_path, template_name="minimal", template_version="0.0.1")
    assert set(lock.keys()) == {"a.py", "nested/b.py"}
    for entry in lock.values():
        assert entry["source_module"] == "template:minimal"
        assert entry["source_version"] == "0.0.1"
        assert entry["forked"] is False


def test_lock_skips_state_dir(tmp_path: Path):
    """`.agentforge-state/` itself isn't tracked by the lock — it's
    the state dir."""
    (tmp_path / ".agentforge-state").mkdir()
    (tmp_path / ".agentforge-state" / "answers.yml").write_text("x: 1")
    (tmp_path / "real.py").write_text("y = 1")

    lock = write_managed_files_lock(tmp_path, template_name="t", template_version="0")
    assert "real.py" in lock
    assert not any(k.startswith(".agentforge-state") for k in lock)


def test_prepend_markers_adds_header_idempotent(tmp_path: Path):
    (tmp_path / "x.py").write_text("body\n")
    write_managed_files_lock(tmp_path, template_name="minimal", template_version="0.0.1")

    prepend_markers(tmp_path, template_name="minimal", template_version="0.0.1")
    first = (tmp_path / "x.py").read_text()
    assert first.startswith("# AGENTFORGE-MANAGED: template:minimal@0.0.1 hash:")
    assert "body" in first

    # Re-running doesn't re-prepend.
    prepend_markers(tmp_path, template_name="minimal", template_version="0.0.1")
    second = (tmp_path / "x.py").read_text()
    assert first == second


# --- file_status ---------------------------------------------


def test_file_status_managed(tmp_path: Path):
    (tmp_path / "x.py").write_text("body\n")
    write_managed_files_lock(tmp_path, template_name="t", template_version="0")
    prepend_markers(tmp_path, template_name="t", template_version="0")
    lock = read_lock(tmp_path)
    assert file_status(tmp_path, "x.py", lock["x.py"]) == "managed"


def test_file_status_drifted_after_edit(tmp_path: Path):
    (tmp_path / "x.py").write_text("body\n")
    write_managed_files_lock(tmp_path, template_name="t", template_version="0")
    prepend_markers(tmp_path, template_name="t", template_version="0")
    lock = read_lock(tmp_path)
    # User edits the file.
    (tmp_path / "x.py").write_text("# AGENTFORGE-MANAGED: ...\nedited\n")
    assert file_status(tmp_path, "x.py", lock["x.py"]) == "drifted"


def test_file_status_missing(tmp_path: Path):
    (tmp_path / "x.py").write_text("body\n")
    write_managed_files_lock(tmp_path, template_name="t", template_version="0")
    lock = read_lock(tmp_path)
    (tmp_path / "x.py").unlink()
    assert file_status(tmp_path, "x.py", lock["x.py"]) == "missing"


def test_file_status_forked_flag_wins(tmp_path: Path):
    (tmp_path / "x.py").write_text("body\n")
    write_managed_files_lock(tmp_path, template_name="t", template_version="0")
    lock = read_lock(tmp_path)
    lock["x.py"]["forked"] = True
    assert file_status(tmp_path, "x.py", lock["x.py"]) == "forked"


# --- strip_marker --------------------------------------------


def test_strip_marker_removes_header(tmp_path: Path):
    path = tmp_path / "x.py"
    path.write_text("# AGENTFORGE-MANAGED: t@0 hash:abc\nbody\n")
    assert strip_marker(path) is True
    assert path.read_text() == "body\n"


def test_strip_marker_noop_when_absent(tmp_path: Path):
    path = tmp_path / "x.py"
    path.write_text("body\n")
    assert strip_marker(path) is False
    assert path.read_text() == "body\n"


# --- agentforge new writes lock + markers --------------------


def test_new_command_writes_lock_and_markers(tmp_path: Path):
    dst = tmp_path / "test-agent"
    code = _run_new(
        argparse.Namespace(
            project_slug="test-agent",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    assert code == 0
    lock = read_lock(dst)
    assert lock  # non-empty
    assert "agentforge.yaml" in lock
    # Marker prepended to every supported file.
    body = (dst / "agentforge.yaml").read_text()
    assert body.startswith("# AGENTFORGE-MANAGED: template:minimal@")


# --- fork --------------------------------------------------


def test_fork_strips_marker_and_flags(tmp_path: Path):
    dst = tmp_path / "agent"
    _run_new(
        argparse.Namespace(
            project_slug="agent",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    code = _run_fork(argparse.Namespace(path="agentforge.yaml"), cwd=dst)
    assert code == 0
    body = (dst / "agentforge.yaml").read_text()
    assert "AGENTFORGE-MANAGED" not in body
    lock = read_lock(dst)
    assert lock["agentforge.yaml"]["forked"] is True


def test_fork_nonexistent_path_errors(tmp_path: Path, capsys):
    dst = tmp_path / "agent"
    _run_new(
        argparse.Namespace(
            project_slug="agent",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    code = _run_fork(argparse.Namespace(path="missing.txt"), cwd=dst)
    assert code == 1
    assert "not in the managed-files lock" in capsys.readouterr().err


# --- unfork ------------------------------------------------


def test_unfork_clears_flag(tmp_path: Path):
    dst = tmp_path / "agent"
    _run_new(
        argparse.Namespace(
            project_slug="agent",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    _run_fork(argparse.Namespace(path="agentforge.yaml"), cwd=dst)
    code = _run_unfork(argparse.Namespace(path="agentforge.yaml"), cwd=dst)
    assert code == 0
    lock = read_lock(dst)
    assert lock["agentforge.yaml"]["forked"] is False
    # Marker re-prepended.
    assert (dst / "agentforge.yaml").read_text().startswith("# AGENTFORGE-MANAGED")


def test_unfork_unforked_errors(tmp_path: Path, capsys):
    dst = tmp_path / "agent"
    _run_new(
        argparse.Namespace(
            project_slug="agent",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    code = _run_unfork(argparse.Namespace(path="agentforge.yaml"), cwd=dst)
    assert code == 1
    assert "not forked" in capsys.readouterr().err


# --- status ----------------------------------------------


def test_status_reports_each_category(tmp_path: Path, capsys):
    dst = tmp_path / "agent"
    _run_new(
        argparse.Namespace(
            project_slug="agent",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    # Fork one file.
    _run_fork(argparse.Namespace(path="agentforge.yaml"), cwd=dst)
    capsys.readouterr()  # drain

    # Drift another.
    (dst / "README.md").write_text("hand-edited\n")

    # Delete a third.
    (dst / ".gitignore").unlink()

    code = _run_status(argparse.Namespace(), cwd=dst)
    assert code == 0
    out = capsys.readouterr().out
    assert "FORKED" in out
    assert "DRIFTED" in out
    assert "MISSING" in out


def test_status_empty_repo_handled(tmp_path: Path, capsys):
    code = _run_status(argparse.Namespace(), cwd=tmp_path)
    assert code == 0
    assert "wasn't scaffolded" in capsys.readouterr().out


# --- upgrade dry-run ------------------------------------


def test_upgrade_dry_run_returns_zero(tmp_path: Path, capsys):
    dst = tmp_path / "agent"
    _run_new(
        argparse.Namespace(
            project_slug="agent",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    # Write an answers.yml manually since Copier's auto-write isn't
    # reliable for local-path templates.
    (dst / ".agentforge-state").mkdir(parents=True, exist_ok=True)
    (dst / ".agentforge-state" / "answers.yml").write_text(
        yaml.safe_dump({"_src_path": "fake", "project_slug": "agent"})
    )
    code = _run_upgrade(argparse.Namespace(to=None, dry_run=True), cwd=dst)
    assert code == 0
    assert "dry-run" in capsys.readouterr().out


def test_upgrade_without_answers_file_errors(tmp_path: Path, capsys):
    code = _run_upgrade(argparse.Namespace(to=None, dry_run=False), cwd=tmp_path)
    assert code == 1
    assert "answers.yml" in capsys.readouterr().err


# --- lock_path is stable -------------------------------


def test_lock_path_is_under_state_dir(tmp_path: Path):
    assert lock_path(tmp_path).parts[-3:] == (
        tmp_path.name,
        ".agentforge-state",
        "managed-files.lock",
    )


# --- hash_content is stable ---------------------------


def test_hash_content_deterministic():
    assert hash_content("hello") == hash_content("hello")
    assert hash_content("a") != hash_content("b")
