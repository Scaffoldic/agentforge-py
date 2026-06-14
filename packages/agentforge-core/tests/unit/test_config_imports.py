"""Unit tests for the `imports:` config-sources directive (feat-026
Phase 3).

`imports:` is a top-level loader directive: a list of other config files
to pull in. Imported files flow through the same machinery as the base
file (interpolation, env-overlay layering, `--override`, `--resolved`,
validation) and sit at **lower precedence than the importing file**
(Spring `spring.config.import` semantics). The directive is consumed by
the loader, so it never reaches the strict root model.

These tests write real files to `tmp_path` and load them for real — no
mocking of the filesystem or the loader.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge_core.config import load_config
from agentforge_core.production.exceptions import ModuleError
from pydantic import BaseModel, ConfigDict


def _write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


# --- basic merge + precedence ------------------------------------


def test_import_merges_into_base(tmp_path: Path) -> None:
    _write(tmp_path / "shared.yaml", "agent:\n  model: shared-model\n  max_iterations: 7\n")
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - shared.yaml\n")
    cfg = load_config(base)
    assert cfg.agent.model == "shared-model"
    assert cfg.agent.max_iterations == 7


def test_importing_file_wins_over_import(tmp_path: Path) -> None:
    """Spring semantics: the file doing the importing overrides what it
    imports (import defaults, override locally)."""
    _write(tmp_path / "shared.yaml", "agent:\n  model: shared-model\n  max_iterations: 7\n")
    base = _write(
        tmp_path / "agentforge.yaml",
        "imports:\n  - shared.yaml\nagent:\n  model: local-model\n",
    )
    cfg = load_config(base)
    assert cfg.agent.model == "local-model"  # local wins
    assert cfg.agent.max_iterations == 7  # inherited from import


def test_later_import_beats_earlier(tmp_path: Path) -> None:
    _write(tmp_path / "a.yaml", "agent:\n  model: from-a\n")
    _write(tmp_path / "b.yaml", "agent:\n  model: from-b\n")
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - a.yaml\n  - b.yaml\n")
    cfg = load_config(base)
    assert cfg.agent.model == "from-b"


def test_deep_merge_across_import_boundary(tmp_path: Path) -> None:
    """Nested mappings merge key-by-key across the import boundary."""
    _write(
        tmp_path / "shared.yaml",
        "agent:\n  model: shared-model\n  budget:\n    usd: 9.0\n",
    )
    base = _write(
        tmp_path / "agentforge.yaml",
        "imports:\n  - shared.yaml\nagent:\n  name: local\n",
    )
    cfg = load_config(base)
    assert cfg.agent.name == "local"
    assert cfg.agent.model == "shared-model"
    assert cfg.agent.budget.usd == pytest.approx(9.0)


# --- transitive + cycles -----------------------------------------


def test_transitive_imports(tmp_path: Path) -> None:
    _write(tmp_path / "c.yaml", "agent:\n  model: from-c\n  max_iterations: 3\n")
    _write(tmp_path / "b.yaml", "imports:\n  - c.yaml\nagent:\n  name: b-named\n")
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - b.yaml\n")
    cfg = load_config(base)
    assert cfg.agent.model == "from-c"
    assert cfg.agent.name == "b-named"
    assert cfg.agent.max_iterations == 3


def test_circular_import_raises(tmp_path: Path) -> None:
    _write(tmp_path / "a.yaml", "imports:\n  - b.yaml\n")
    _write(tmp_path / "b.yaml", "imports:\n  - a.yaml\n")
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - a.yaml\n")
    with pytest.raises(ModuleError, match="Circular config import"):
        load_config(base)


def test_self_import_raises(tmp_path: Path) -> None:
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - agentforge.yaml\n")
    with pytest.raises(ModuleError, match="Circular config import"):
        load_config(base)


# --- path resolution + errors ------------------------------------


def test_relative_path_resolves_against_importer_dir(tmp_path: Path) -> None:
    sub = tmp_path / "conf"
    sub.mkdir()
    _write(sub / "shared.yaml", "agent:\n  model: sub-model\n")
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - conf/shared.yaml\n")
    cfg = load_config(base)
    assert cfg.agent.model == "sub-model"


def test_absolute_import_path(tmp_path: Path) -> None:
    shared = _write(tmp_path / "shared.yaml", "agent:\n  model: abs-model\n")
    base = _write(tmp_path / "agentforge.yaml", f"imports:\n  - {shared}\n")
    cfg = load_config(base)
    assert cfg.agent.model == "abs-model"


def test_missing_import_raises(tmp_path: Path) -> None:
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - nope.yaml\n")
    with pytest.raises(ModuleError, match="Imported config file not found"):
        load_config(base)


def test_non_list_imports_raises(tmp_path: Path) -> None:
    base = _write(tmp_path / "agentforge.yaml", "imports: shared.yaml\n")
    with pytest.raises(ModuleError, match="must be a list"):
        load_config(base)


def test_non_string_import_entry_raises(tmp_path: Path) -> None:
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - {path: shared.yaml}\n")
    with pytest.raises(ModuleError, match="must be strings"):
        load_config(base)


# --- composition with the rest of the pipeline -------------------


def test_env_interpolation_in_import_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path / "shared.yaml", "agent:\n  model: env-pathed\n")
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - ${SHARED_FILE}\n")
    monkeypatch.setenv("SHARED_FILE", str(tmp_path / "shared.yaml"))
    cfg = load_config(base)
    assert cfg.agent.model == "env-pathed"


def test_env_interpolation_in_imported_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Values *inside* an imported file get `${ENV}` interpolation, same
    as the base file (the whole merged tree is walked once)."""
    _write(tmp_path / "shared.yaml", "agent:\n  model: ${MODEL:fallback}\n")
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - shared.yaml\n")
    monkeypatch.setenv("MODEL", "interpolated-model")
    cfg = load_config(base)
    assert cfg.agent.model == "interpolated-model"


def test_override_still_wins_over_imports(tmp_path: Path) -> None:
    _write(tmp_path / "shared.yaml", "agent:\n  budget:\n    usd: 5.0\n")
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - shared.yaml\n")
    cfg = load_config(base, overrides=["agent.budget.usd=42"])
    assert cfg.agent.budget.usd == pytest.approx(42.0)


def test_env_overlay_is_import_aware(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path / "prod-shared.yaml", "agent:\n  model: prod-shared-model\n")
    _write(tmp_path / "agentforge.yaml", "agent:\n  model: base-model\n")
    _write(
        tmp_path / "agentforge.production.yaml",
        "imports:\n  - prod-shared.yaml\n",
    )
    monkeypatch.setenv("AGENTFORGE_ENV", "production")
    cfg = load_config(tmp_path / "agentforge.yaml")
    # Overlay imports prod-shared, and the overlay layer (incl. its
    # imports) beats the base file.
    assert cfg.agent.model == "prod-shared-model"


def test_imports_key_consumed_not_in_resolved(tmp_path: Path) -> None:
    """`imports:` is a loader directive — it must not survive into the
    validated model (which is `extra="forbid"`) or the resolved dump."""
    _write(tmp_path / "shared.yaml", "agent:\n  model: m\n")
    base = _write(tmp_path / "agentforge.yaml", "imports:\n  - shared.yaml\n")
    cfg = load_config(base)
    assert "imports" not in cfg.model_dump()


def test_app_config_split_into_separate_file(tmp_path: Path) -> None:
    """The #86 motivating scenario: a derived agent keeps its app config
    in its own file and imports it — the framework merges + validates it
    like any other config, no side-loader needed."""

    class StoreConfig(BaseModel):
        model_config = ConfigDict(extra="forbid")
        path: str

    class GraphConfig(BaseModel):
        model_config = ConfigDict(extra="forbid")
        store: StoreConfig

    _write(tmp_path / "graph.yaml", "app:\n  graph:\n    store:\n      path: .ckg\n")
    base = _write(
        tmp_path / "agentforge.yaml",
        "imports:\n  - graph.yaml\nagent:\n  model: my-model\n",
    )
    cfg = load_config(base)
    assert cfg.agent.model == "my-model"
    graph = cfg.app_as(GraphConfig, "graph")
    assert graph.store.path == ".ckg"
