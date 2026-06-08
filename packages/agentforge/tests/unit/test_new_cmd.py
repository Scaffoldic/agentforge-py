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
    assert "my-agent" in main_py  # kebab slug in the Usage hint

    # The kebab→snake transform produces the right console-script
    # entry point in pyproject.toml.
    pyproject = (dst / "pyproject.toml").read_text()
    assert "my_agent.main:main" in pyproject

    # Lock file + answers file are written by chunk 3
    # (`.agentforge-state/` plumbing).


def test_scaffold_records_real_framework_version(tmp_path: Path):
    """bug-008: the lock/answers `_template_version` must be the real
    installed framework version, not the `0.0.0+unknown` sentinel — the
    version lookup keys off the distribution name `agentforge-py`."""
    from importlib.metadata import version  # noqa: PLC0415

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
    answers = yaml.safe_load((dst / ".agentforge-state" / "answers.yml").read_text())
    assert answers["_template_version"] != "0.0.0+unknown"
    assert answers["_template_version"] == version("agentforge-py")


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


@pytest.mark.parametrize(
    "template",
    ["minimal", "code-reviewer", "patch-bot", "docs-qa", "triage", "research"],
)
def test_every_shipped_template_renders(tmp_path: Path, template: str):
    """Every template ships a working scaffold — Copier renders
    cleanly with `--no-prompts` and produces the expected files."""
    dst = tmp_path / f"check-{template}"
    code = _run_new(
        argparse.Namespace(
            project_slug=f"check-{template}",
            template=template,
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    assert code == 0
    # Every template must produce these three at the project root.
    assert (dst / "agentforge.yaml").exists()
    assert (dst / "pyproject.toml").exists()
    assert (dst / "README.md").exists()


def test_scaffold_ships_ai_assistant_instructions(tmp_path: Path):
    """Every scaffolded agent gets framework-aware instructions for
    Claude Code, Cursor, Aider/agents.md tools, and GitHub Copilot —
    so the developer's AI assistant follows the framework's runbooks
    out of the box. Regression guard: missing one of these means a
    user's AI helper hallucinates another framework's idioms instead of using
    AgentForge's locked contracts."""
    dst = tmp_path / "ai-assist-check"
    code = _run_new(
        argparse.Namespace(
            project_slug="ai-assist-check",
            template="minimal",
            provider="bedrock",
            no_prompts=True,
            dst=dst,
        )
    )
    assert code == 0
    assert (dst / "AGENTS.md").exists(), "agents.md convention file"
    assert (dst / "CLAUDE.md").exists(), "Claude Code discovery"
    assert (dst / ".cursorrules").exists(), "Cursor discovery"
    assert (dst / ".github" / "copilot-instructions.md").exists(), "GitHub Copilot discovery"
    assert (dst / "docs" / "runbooks").is_dir(), "runbook catalogue"


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


def test_scaffold_resolves_runnable_end_to_end(tmp_path: Path):
    """Regression for bugs 001, 002, 003, 006 — the scaffolded agent
    must contain everything needed to run end-to-end after
    ``uv sync`` + ``cp .env.example .env``. Together, these checks
    lock in:

    - bug-001: provider package + SDK extra in pyproject deps.
    - bug-002: default reasoning strategy in agentforge.yaml.
    - bug-003: console-script entry in pyproject [project.scripts].
    - bug-006: load_dotenv() in main.py.
    """
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

    pyproject = (dst / "pyproject.toml").read_text()
    # bug-001 — provider's SDK extra reaches the agent's deps.
    assert "agentforge-anthropic[anthropic]" in pyproject
    # bug-006 — python-dotenv shipped so .env loading works.
    assert "python-dotenv" in pyproject
    # bug-003 — agent is invokable as a CLI command.
    assert "[project.scripts]" in pyproject
    assert "agent.main:main" in pyproject

    # bug-002 — default reasoning strategy is wired.
    cfg = yaml.safe_load((dst / "agentforge.yaml").read_text())
    assert cfg["agent"].get("strategy"), "agentforge.yaml missing agent.strategy"

    # bug-006 — main.py actually calls load_dotenv().
    main_py = (dst / "src" / "agent" / "main.py").read_text()
    assert "from dotenv import load_dotenv" in main_py
    assert "load_dotenv()" in main_py
