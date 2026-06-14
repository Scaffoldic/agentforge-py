"""Unit tests for the reserved ``app:`` passthrough namespace
(enh-002, feat-026 Phase 1).

The framework accepts an ``app:`` subtree in ``agentforge.yaml`` but
does not interpret it: a consuming agent validates that subtree with
its own Pydantic model via :meth:`AgentForgeConfig.app_as`. Every other
top-level key stays strict (``extra="forbid"``). Values under ``app:``
ride the same loader passes as framework keys, so they get ``${ENV}``
interpolation, env-file layering, and ``config show --resolved`` for
free.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge_core.config import AgentForgeConfig, load_config
from pydantic import BaseModel, ConfigDict, ValidationError

# --- the field exists and defaults to {} -------------------------


def test_app_defaults_to_empty_mapping() -> None:
    cfg = AgentForgeConfig()
    assert cfg.app == {}


def test_app_block_is_accepted(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text(
        """
agent:
  model: anthropic:claude-haiku-4-5
app:
  graph:
    store:
      path: .ckg
"""
    )
    cfg = load_config(yaml_path)
    assert cfg.app["graph"]["store"]["path"] == ".ckg"


# --- typo protection on framework keys is unchanged --------------


def test_unknown_root_key_outside_app_still_rejected(tmp_path: Path) -> None:
    """A stray top-level key (not ``app``) still fails strict validation —
    typo protection is intact."""
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("graph:\n  store:\n    path: .ckg\n")
    with pytest.raises(ValidationError) as exc:
        load_config(yaml_path)
    assert "graph" in str(exc.value)


# --- app_as: typed + validated subtree ---------------------------


class _StoreConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str


class _GraphConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store: _StoreConfig


def test_app_as_validates_keyed_subtree(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("app:\n  graph:\n    store:\n      path: .ckg\n")
    cfg = load_config(yaml_path)
    graph_cfg = cfg.app_as(_GraphConfig, "graph")
    assert isinstance(graph_cfg, _GraphConfig)
    assert graph_cfg.store.path == ".ckg"


def test_app_as_whole_block_when_key_none(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("app:\n  store:\n    path: .ckg\n")
    cfg = load_config(yaml_path)
    whole = cfg.app_as(_GraphConfig)
    assert whole.store.path == ".ckg"


def test_app_as_missing_key_yields_empty_mapping() -> None:
    """An absent app key validates against an empty mapping, so the
    caller's model supplies its own defaults (or raises if required)."""

    class _Defaulted(BaseModel):
        flag: bool = True

    cfg = AgentForgeConfig()
    assert cfg.app_as(_Defaulted, "missing").flag is True


def test_app_as_delegates_strictness_to_caller_model(tmp_path: Path) -> None:
    """A typo *inside* ``app:`` is caught by the caller's own
    ``extra="forbid"`` model — strictness is delegated, not lost."""
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("app:\n  graph:\n    stop:\n      path: .ckg\n")
    cfg = load_config(yaml_path)
    with pytest.raises(ValidationError):
        cfg.app_as(_GraphConfig, "graph")


# --- app: rides the loader passes (interpolation + layering) -----


def test_env_interpolation_resolves_inside_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("app:\n  graph:\n    store:\n      path: ${CKG_PATH:.ckg}\n")
    monkeypatch.setenv("CKG_PATH", "/data/ckg")
    cfg = load_config(yaml_path)
    assert cfg.app["graph"]["store"]["path"] == "/data/ckg"


def test_env_interpolation_default_inside_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("app:\n  graph:\n    store:\n      path: ${CKG_PATH:.ckg}\n")
    monkeypatch.delenv("CKG_PATH", raising=False)
    cfg = load_config(yaml_path)
    assert cfg.app["graph"]["store"]["path"] == ".ckg"


def test_env_file_layering_overrides_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "agentforge.yaml"
    base.write_text("app:\n  graph:\n    store:\n      path: .ckg\n")
    overlay = tmp_path / "agentforge.production.yaml"
    overlay.write_text("app:\n  graph:\n    store:\n      path: /srv/ckg\n")
    monkeypatch.setenv("AGENTFORGE_ENV", "production")
    cfg = load_config(base)
    assert cfg.app["graph"]["store"]["path"] == "/srv/ckg"


# --- config show --resolved includes app -------------------------


def test_model_dump_includes_resolved_app(tmp_path: Path) -> None:
    """``config show --resolved`` dumps ``cfg.model_dump(mode="json")``,
    so the resolved ``app:`` subtree is emitted for free."""
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("app:\n  graph:\n    store:\n      path: .ckg\n")
    cfg = load_config(yaml_path)
    dumped = cfg.model_dump(mode="json")
    assert dumped["app"]["graph"]["store"]["path"] == ".ckg"
