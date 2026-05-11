"""Unit tests for the YAML loader + env-var interpolation + schema."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge.config import AgentForgeConfig, load_config
from agentforge_core.production.exceptions import ModuleError
from pydantic import ValidationError


def test_default_config_when_no_file_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGENTFORGE_CONFIG", raising=False)
    cfg = load_config()
    assert isinstance(cfg, AgentForgeConfig)
    assert cfg.agent.budget.usd == 1.0
    assert cfg.agent.max_iterations == 25
    assert cfg.logging.run_id_filter is True


def test_loads_explicit_path(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text(
        "agent:\n"
        "  model: anthropic:claude-sonnet-4.7\n"
        "  budget:\n    usd: 5.0\n"
        "  max_iterations: 50\n"
    )
    cfg = load_config(yaml_path)
    assert cfg.agent.model == "anthropic:claude-sonnet-4.7"
    assert cfg.agent.budget.usd == pytest.approx(5.0)
    assert cfg.agent.max_iterations == 50


def test_env_var_interpolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_MODEL", "anthropic:claude-haiku-4-5")
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  model: ${MY_MODEL}\n")
    cfg = load_config(yaml_path)
    assert cfg.agent.model == "anthropic:claude-haiku-4-5"


def test_env_var_default_used_when_unset(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  model: ${UNSET_VAR:fallback}\n")
    cfg = load_config(yaml_path)
    assert cfg.agent.model == "fallback"


def test_env_var_required_with_error_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("REQUIRED_KEY", raising=False)
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  model: ${REQUIRED_KEY:?Set REQUIRED_KEY}\n")
    with pytest.raises(ModuleError, match="Required env var REQUIRED_KEY"):
        load_config(yaml_path)


def test_env_var_required_no_default_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("UNSET_REQUIRED", raising=False)
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  model: ${UNSET_REQUIRED}\n")
    with pytest.raises(ModuleError, match="not set"):
        load_config(yaml_path)


def test_double_dollar_escape(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  system_prompt: 'Cost is $$5'\n")
    cfg = load_config(yaml_path)
    assert cfg.agent.system_prompt == "Cost is $5"


def test_unknown_top_level_key_rejected(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("unknown_section:\n  foo: bar\n")
    with pytest.raises(ValidationError):
        load_config(yaml_path)


def test_invalid_yaml_top_level_raises(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("- just a list\n- not a mapping\n")
    with pytest.raises(ModuleError, match="must be a mapping"):
        load_config(yaml_path)


def test_negative_budget_rejected(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  budget:\n    usd: -1.0\n")
    with pytest.raises(ValidationError):
        load_config(yaml_path)


def test_flat_budget_usd_no_longer_valid(tmp_path: Path) -> None:
    """feat-012 deprecates the flat `agent.budget_usd: float` form in
    favour of nested `agent.budget.usd`. The schema now rejects the
    flat field as `extra="forbid"`."""
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  budget_usd: 5.0\n")
    with pytest.raises(ValidationError, match="budget_usd"):
        load_config(yaml_path)
