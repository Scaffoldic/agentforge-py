"""Unit tests for `agentforge config {validate,show,schema}`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest
import yaml
from agentforge.cli.main import main
from agentforge_core import Resolver, register
from agentforge_core.resolver import discover as discover_mod
from pydantic import BaseModel, ConfigDict


@pytest.fixture(autouse=True)
def _resolver_snapshot():
    resolver = Resolver.global_()
    resolver.list_installed()  # trigger discovery before snapshot
    saved_registry = dict(resolver._registry)
    saved_module_info = dict(discover_mod._module_info_cache)
    saved_flag = discover_mod._discovered[0]
    yield
    resolver.clear()
    resolver._registry.update(saved_registry)
    discover_mod._module_info_cache.clear()
    discover_mod._module_info_cache.update(saved_module_info)
    discover_mod._discovered[0] = saved_flag


# --- validate -----------------------------------------------------


def test_validate_happy_path(tmp_path: Path, capsys) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  model: anthropic:claude-sonnet-4.7\n  budget:\n    usd: 5.0\n")
    code = main(["config", "validate", "--path", str(yaml_path)])
    assert code == 0
    assert "OK" in capsys.readouterr().out


def test_validate_reports_pydantic_error_path(tmp_path: Path, capsys) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  budget_usd: 5.0\n")  # old flat field
    code = main(["config", "validate", "--path", str(yaml_path)])
    assert code == 1
    err = capsys.readouterr().err
    assert "agent.budget_usd" in err
    assert "Extra inputs" in err or "not permitted" in err


def test_validate_reports_load_error_for_required_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  model: ${NEEDED}\n")
    monkeypatch.delenv("NEEDED", raising=False)
    code = main(["config", "validate", "--path", str(yaml_path)])
    assert code == 1
    assert "NEEDED" in capsys.readouterr().err


def test_validate_overrides_applied(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  budget:\n    usd: 1.0\n")
    # Override turns a valid config into one with a negative budget.
    code = main(
        [
            "config",
            "validate",
            "--path",
            str(yaml_path),
            "--override",
            "agent.budget.usd=-5",
        ]
    )
    assert code == 1


def test_validate_module_schema_lenient_by_default(tmp_path: Path) -> None:
    """Missing modules are skipped in lenient mode (the default)."""
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("modules:\n  memory:\n    driver: nonexistent\n    config: {}\n")
    code = main(["config", "validate", "--path", str(yaml_path)])
    assert code == 0


def test_validate_strict_modules_flag_rejects_missing(tmp_path: Path, capsys) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("modules:\n  memory:\n    driver: nonexistent\n    config: {}\n")
    code = main(["config", "validate", "--path", str(yaml_path), "--strict-modules"])
    assert code == 1
    assert "No module registered" in capsys.readouterr().err


def test_validate_module_config_against_schema(tmp_path: Path, capsys) -> None:
    class _PostgresConfig(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")
        dsn: str

    class _PostgresStore:
        config_schema: ClassVar[type[BaseModel]] = _PostgresConfig

    register("memory", "postgres-cli-test")(_PostgresStore)

    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text(
        "modules:\n"
        "  memory:\n"
        "    driver: postgres-cli-test\n"
        "    config:\n"
        "      dsn: 42\n"  # wrong type
    )
    code = main(["config", "validate", "--path", str(yaml_path)])
    assert code == 1
    assert "modules.memory.config" in capsys.readouterr().err


# --- show ---------------------------------------------------------


def test_show_resolved_default(tmp_path: Path, capsys) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  model: ${MY_MODEL:default-model}\n")
    code = main(["config", "show", "--path", str(yaml_path)])
    assert code == 0
    out = capsys.readouterr().out
    # Env var was unset, so default got applied.
    parsed = yaml.safe_load(out)
    assert parsed["agent"]["model"] == "default-model"


def test_show_raw_skips_interpolation(tmp_path: Path, capsys) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  model: ${MY_MODEL:default-model}\n")
    code = main(["config", "show", "--path", str(yaml_path), "--raw"])
    assert code == 0
    out = capsys.readouterr().out
    # Raw output should contain the un-interpolated env reference.
    assert "${MY_MODEL:default-model}" in out


def test_show_raw_missing_file(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "does_not_exist.yaml"
    code = main(["config", "show", "--path", str(missing), "--raw"])
    assert code == 1
    assert "no config file" in capsys.readouterr().err


def test_show_applies_overrides(tmp_path: Path, capsys) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  budget:\n    usd: 1.0\n")
    code = main(
        [
            "config",
            "show",
            "--path",
            str(yaml_path),
            "--override",
            "agent.budget.usd=42.5",
        ]
    )
    assert code == 0
    parsed = yaml.safe_load(capsys.readouterr().out)
    assert parsed["agent"]["budget"]["usd"] == 42.5


# --- schema -------------------------------------------------------


def test_schema_emits_json(capsys) -> None:
    code = main(["config", "schema"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["title"] == "AgentForgeConfig"
    # Sanity-check the widened shape made it into the schema.
    assert "agent" in payload["properties"]
    assert "modules" in payload["properties"]
    assert "providers" in payload["properties"]


def test_schema_indent_flag(capsys) -> None:
    code = main(["config", "schema", "--indent", "0"])
    assert code == 0
    out = capsys.readouterr().out
    # indent=0 still emits each value on its own line; just no leading
    # whitespace at the inner levels.
    assert "\n" in out
    # Reparseable.
    json.loads(out)
