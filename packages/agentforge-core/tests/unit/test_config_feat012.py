"""Unit tests for feat-012 loader features (layered files, dotted
overrides, env shortcuts, widened schema)."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge_core.config import (
    AgentForgeConfig,
    BudgetConfig,
    ModulesConfig,
    load_config,
    parse_overrides,
)
from agentforge_core.production.exceptions import ModuleError

# --- widened schema ----------------------------------------------


def test_default_root_has_full_shape():
    cfg = AgentForgeConfig()
    assert isinstance(cfg.modules, ModulesConfig)
    assert isinstance(cfg.agent.budget, BudgetConfig)
    assert cfg.providers == {}
    assert cfg.output.default_finding_variant == "simple"


def test_modules_section_loads(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text(
        """
agent:
  model: anthropic:claude-sonnet-4.7
modules:
  memory:
    driver: postgres
    config:
      dsn: "postgresql://localhost/db"
  evaluators:
    - name: faithfulness
    - name: geval
      config:
        rubric: code-review
        cost_cap_usd: 0.2
  observability:
    - name: otel
      config:
        endpoint: "http://localhost:4317"
"""
    )
    cfg = load_config(yaml_path)
    assert cfg.modules.memory is not None
    assert cfg.modules.memory.driver == "postgres"
    assert cfg.modules.memory.config["dsn"] == "postgresql://localhost/db"
    assert [e.name for e in cfg.modules.evaluators] == ["faithfulness", "geval"]
    assert cfg.modules.evaluators[1].config["rubric"] == "code-review"
    assert cfg.modules.observability[0].name == "otel"


def test_providers_section_loads(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text(
        """
providers:
  reasoning:
    type: anthropic
    model: claude-sonnet-4.7
  fast-judge:
    type: anthropic
    model: claude-haiku-4-5
"""
    )
    cfg = load_config(yaml_path)
    assert "reasoning" in cfg.providers
    assert cfg.providers["reasoning"].type == "anthropic"
    assert cfg.providers["fast-judge"].model == "claude-haiku-4-5"


def test_system_prompt_file_loads_as_path(tmp_path: Path) -> None:
    prompt = tmp_path / "system.md"
    prompt.write_text("system text")
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text(f"agent:\n  system_prompt_file: {prompt}\n")
    cfg = load_config(yaml_path)
    assert cfg.agent.system_prompt_file == prompt


# --- layered env files ------------------------------------------


def test_overlay_merges_via_agentforge_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "agentforge.yaml"
    base.write_text(
        """
agent:
  model: anthropic:claude-sonnet-4.7
  budget:
    usd: 1.0
modules:
  memory:
    driver: sqlite
    config:
      path: "./agent.db"
"""
    )
    overlay = tmp_path / "agentforge.production.yaml"
    overlay.write_text(
        """
agent:
  budget:
    usd: 50.0
modules:
  memory:
    driver: postgres
    config:
      dsn: "postgresql://prod/db"
"""
    )
    monkeypatch.setenv("AGENTFORGE_ENV", "production")
    cfg = load_config(base)
    # Overlay wins where keys overlap.
    assert cfg.agent.budget.usd == pytest.approx(50.0)
    # Model came from base (overlay didn't touch it).
    assert cfg.agent.model == "anthropic:claude-sonnet-4.7"
    # Driver swapped to postgres; config dict deep-merged.
    assert cfg.modules.memory is not None
    assert cfg.modules.memory.driver == "postgres"
    assert cfg.modules.memory.config["dsn"] == "postgresql://prod/db"


def test_overlay_lists_replace_not_append(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "agentforge.yaml"
    base.write_text("modules:\n  evaluators:\n    - name: faithfulness\n    - name: correctness\n")
    overlay = tmp_path / "agentforge.staging.yaml"
    overlay.write_text("modules:\n  evaluators:\n    - name: hallucination\n")
    monkeypatch.setenv("AGENTFORGE_ENV", "staging")
    cfg = load_config(base)
    assert [e.name for e in cfg.modules.evaluators] == ["hallucination"]


def test_missing_overlay_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When `AGENTFORGE_ENV` is set but the overlay file doesn't
    exist, the base config loads cleanly — no error."""
    base = tmp_path / "agentforge.yaml"
    base.write_text("agent:\n  model: anthropic:claude-sonnet-4.7\n")
    monkeypatch.setenv("AGENTFORGE_ENV", "nonexistent")
    cfg = load_config(base)
    assert cfg.agent.model == "anthropic:claude-sonnet-4.7"


# --- dotted-path overrides --------------------------------------


def test_parse_overrides_simple():
    out = parse_overrides(["agent.budget.usd=10", "agent.max_iterations=5"])
    assert out == {"agent": {"budget": {"usd": 10}, "max_iterations": 5}}


def test_parse_overrides_yaml_values():
    """Values get YAML-parsed — bools, floats, lists work."""
    out = parse_overrides(
        [
            "logging.run_id_filter=false",
            "agent.budget.usd=2.5",
            "modules.tools=[a, b, c]",
        ]
    )
    assert out["logging"]["run_id_filter"] is False
    assert out["agent"]["budget"]["usd"] == 2.5
    assert out["modules"]["tools"] == ["a", "b", "c"]


def test_parse_overrides_rejects_missing_eq():
    with pytest.raises(ModuleError, match="<path>=<value>"):
        parse_overrides(["agent.budget.usd"])


def test_parse_overrides_rejects_empty_path():
    with pytest.raises(ModuleError, match="empty path"):
        parse_overrides(["=10"])


def test_parse_overrides_rejects_empty_segment():
    with pytest.raises(ModuleError, match="empty path segment"):
        parse_overrides(["agent..usd=10"])


def test_load_config_applies_overrides(tmp_path: Path) -> None:
    base = tmp_path / "agentforge.yaml"
    base.write_text("agent:\n  budget:\n    usd: 1.0\n")
    cfg = load_config(base, overrides=["agent.budget.usd=99.5"])
    assert cfg.agent.budget.usd == pytest.approx(99.5)


def test_overrides_beat_env_overlay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolution order per spec §4.3: overrides apply after env
    overlay merge, so they win."""
    base = tmp_path / "agentforge.yaml"
    base.write_text("agent:\n  budget:\n    usd: 1.0\n")
    overlay = tmp_path / "agentforge.dev.yaml"
    overlay.write_text("agent:\n  budget:\n    usd: 20.0\n")
    monkeypatch.setenv("AGENTFORGE_ENV", "dev")
    cfg = load_config(base, overrides=["agent.budget.usd=999"])
    assert cfg.agent.budget.usd == 999


# --- env shortcuts ----------------------------------------------


def test_agentforge_config_env_overrides_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    elsewhere = tmp_path / "subdir" / "custom.yaml"
    elsewhere.parent.mkdir()
    elsewhere.write_text("agent:\n  model: from-elsewhere\n")
    monkeypatch.setenv("AGENTFORGE_CONFIG", str(elsewhere))
    cfg = load_config()
    assert cfg.agent.model == "from-elsewhere"


def test_explicit_path_beats_agentforge_config_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit = tmp_path / "explicit.yaml"
    explicit.write_text("agent:\n  model: explicit\n")
    other = tmp_path / "other.yaml"
    other.write_text("agent:\n  model: other\n")
    monkeypatch.setenv("AGENTFORGE_CONFIG", str(other))
    cfg = load_config(explicit)
    assert cfg.agent.model == "explicit"


def test_agentforge_log_level_applied_post_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "agentforge.yaml"
    base.write_text("logging:\n  level: INFO\n")
    monkeypatch.setenv("AGENTFORGE_LOG_LEVEL", "DEBUG")
    cfg = load_config(base)
    assert cfg.logging.level == "DEBUG"


def test_agentforge_log_level_unset_keeps_yaml_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "agentforge.yaml"
    base.write_text("logging:\n  level: WARNING\n")
    monkeypatch.delenv("AGENTFORGE_LOG_LEVEL", raising=False)
    cfg = load_config(base)
    assert cfg.logging.level == "WARNING"


# --- explicit env arg beats AGENTFORGE_ENV ---------------------


def test_explicit_env_arg_beats_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "agentforge.yaml"
    base.write_text("agent:\n  budget:\n    usd: 1.0\n")
    prod_overlay = tmp_path / "agentforge.production.yaml"
    prod_overlay.write_text("agent:\n  budget:\n    usd: 100.0\n")
    staging_overlay = tmp_path / "agentforge.staging.yaml"
    staging_overlay.write_text("agent:\n  budget:\n    usd: 50.0\n")

    monkeypatch.setenv("AGENTFORGE_ENV", "production")
    cfg = load_config(base, env="staging")
    assert cfg.agent.budget.usd == pytest.approx(50.0)


# --- evaluator string-shorthand (normalised since bug-019) -----


def test_evaluator_string_shorthand_loads(tmp_path: Path) -> None:
    """Spec §4.1's `evaluators: - faithfulness` (bare string) now loads
    end-to-end: the entry's `mode="before"` validator normalises the
    string to `{name: faithfulness, config: {}}` (bug-019)."""
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("modules:\n  evaluators:\n    - faithfulness\n")
    cfg = load_config(yaml_path)
    assert [(e.name, e.config) for e in cfg.modules.evaluators] == [("faithfulness", {})]
