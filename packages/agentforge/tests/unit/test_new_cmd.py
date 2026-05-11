"""Unit tests for `agentforge new` (feat-011 chunk 1)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import yaml
from agentforge.cli.new_cmd import _run_new


def test_minimal_template_renders_with_no_prompts(tmp_path: Path, capsys):
    dst = tmp_path / "my-agent"
    code = _run_new(
        argparse.Namespace(
            project_slug="my-agent",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    assert code == 0
    assert dst.exists()

    # Standard files rendered.
    assert (dst / "agentforge.yaml").exists()
    assert (dst / "pyproject.toml").exists()
    assert (dst / "README.md").exists()
    assert (dst / ".env.example").exists()
    assert (dst / ".gitignore").exists()
    assert (dst / "src" / "my_agent" / "__init__.py").exists()
    assert (dst / "src" / "my_agent" / "main.py").exists()

    # Jinja substitutions worked.
    cfg = yaml.safe_load((dst / "agentforge.yaml").read_text())
    assert cfg["agent"]["name"] == "my-agent"
    assert cfg["agent"]["model"].startswith("bedrock:")

    main_py = (dst / "src" / "my_agent" / "main.py").read_text()
    # Templated path-imports + content rendered with the slug.
    assert "{{ project_slug" not in main_py
    assert "my_agent" in main_py  # snake_case import path

    # Lock file + answers file are written by chunk 3
    # (`.agentforge-state/` plumbing).


def test_anthropic_provider_routes_to_correct_model(tmp_path: Path):
    dst = tmp_path / "agent"
    _run_new(
        argparse.Namespace(
            project_slug="agent",
            template="minimal",
            provider="anthropic",
            no_prompts=True,
            dst=dst,
        )
    )
    cfg = yaml.safe_load((dst / "agentforge.yaml").read_text())
    assert cfg["agent"]["model"].startswith("anthropic:")


def test_openai_provider_routes_to_correct_model(tmp_path: Path):
    dst = tmp_path / "agent"
    _run_new(
        argparse.Namespace(
            project_slug="agent",
            template="minimal",
            provider="openai",
            no_prompts=True,
            dst=dst,
        )
    )
    cfg = yaml.safe_load((dst / "agentforge.yaml").read_text())
    assert cfg["agent"]["model"].startswith("openai:")


def test_default_destination_is_cwd_slash_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    code = _run_new(
        argparse.Namespace(
            project_slug="cwd-agent",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=None,
        )
    )
    assert code == 0
    assert (tmp_path / "cwd-agent" / "agentforge.yaml").exists()


def test_unknown_template_errors(tmp_path: Path, capsys):
    code = _run_new(
        argparse.Namespace(
            project_slug="x",
            template="nonexistent",
            provider="bedrock",
            no_prompts=True,
            dst=tmp_path / "x",
        )
    )
    assert code == 1
    assert "not shipped" in capsys.readouterr().err


def test_rendered_python_package_has_underscore_name(tmp_path: Path):
    """Kebab-case slug → snake_case package name in `src/`."""
    dst = tmp_path / "my-pr-reviewer"
    _run_new(
        argparse.Namespace(
            project_slug="my-pr-reviewer",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    assert (dst / "src" / "my_pr_reviewer" / "__init__.py").exists()
    assert not (dst / "src" / "my-pr-reviewer").exists()
