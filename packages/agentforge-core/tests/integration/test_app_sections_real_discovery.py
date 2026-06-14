"""Real end-to-end discovery test for feat-026 Phase 2 — *no* mocking.

`test_config_app_sections.py` (unit) injects a section map or
monkeypatches `entry_points`. This test goes the whole way: it drops a
**real installed distribution** on `sys.path` — a real `.dist-info` with
a real `entry_points.txt` declaring the `agentforge.config_sections`
group, plus a real importable module exposing the schema class — and
exercises the actual `importlib.metadata` discovery path:

- `discover_app_sections()` finds the section via real entry-point
  resolution and `ep.load()` imports the real schema class.
- `validate_app_config()` validates a real `app.<section>` subtree
  against that freshly-imported schema, and rejects a typo.

This is the proof the monkeypatched tests can't give: that a derived
agent declaring `[project.entry-points."agentforge.config_sections"]` in
its own `pyproject.toml` is actually discovered and validated.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess  # nosec B404 — fixed argv, no shell
import sys
import textwrap
from pathlib import Path

import pytest
from agentforge_core.config import (
    AgentForgeConfig,
    discover_app_sections,
    validate_app_config,
)
from agentforge_core.production.exceptions import ModuleError

_MODULE = "af_fake_section_pkg"
_DIST = "af-fake-section"
_SECTION = "graph"
_ATTR = "GraphConfig"


def _install_fake_dist(site: Path) -> None:
    """Lay down a real importable module + a real `.dist-info` whose
    `entry_points.txt` registers our section — the on-disk shape pip / uv
    produce when a package declares the entry point."""
    (site / f"{_MODULE}.py").write_text(
        textwrap.dedent(
            f"""
            from pydantic import BaseModel, ConfigDict

            class _Store(BaseModel):
                model_config = ConfigDict(strict=True, extra="forbid")
                path: str

            class {_ATTR}(BaseModel):
                model_config = ConfigDict(strict=True, extra="forbid")
                store: _Store
                max_hops: int = 3
            """
        )
    )
    dist_info = site / f"{_DIST.replace('-', '_')}-1.0.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {_DIST}\nVersion: 1.0.0\n")
    (dist_info / "entry_points.txt").write_text(
        f"[agentforge.config_sections]\n{_SECTION} = {_MODULE}:{_ATTR}\n"
    )


@pytest.fixture
def fake_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Install the fake distribution on a throwaway site dir, put it on
    `sys.path`, and tear it all down afterwards."""
    site = tmp_path / "site-packages"
    site.mkdir()
    _install_fake_dist(site)
    monkeypatch.syspath_prepend(str(site))
    importlib.invalidate_caches()
    try:
        yield
    finally:
        sys.modules.pop(_MODULE, None)


def test_real_entry_point_is_discovered(fake_section: None) -> None:
    found = discover_app_sections()
    assert _SECTION in found, "real entry point was not discovered via importlib.metadata"
    assert found[_SECTION].__name__ == _ATTR


def test_real_section_validates_ok(fake_section: None) -> None:
    cfg = AgentForgeConfig.model_validate(
        {"app": {_SECTION: {"store": {"path": ".ckg"}, "max_hops": 4}}}
    )
    # Real discovery + real schema, no injected registry → must not raise.
    validate_app_config(cfg)


def test_real_section_typo_is_rejected(fake_section: None) -> None:
    cfg = AgentForgeConfig.model_validate(
        {"app": {_SECTION: {"store": {"path": ".ckg"}, "max_hopz": 4}}}
    )
    with pytest.raises(ModuleError) as exc:
        validate_app_config(cfg)
    assert f"app.{_SECTION}" in str(exc.value)


def test_unregistered_section_untouched_with_real_discovery(fake_section: None) -> None:
    """Even with a real registered `graph` section discovered, an
    *unregistered* sibling section stays free-form."""
    cfg = AgentForgeConfig.model_validate(
        {"app": {"telemetry": {"whatever": "is fine", "deeply": {"nested": 1}}}}
    )
    validate_app_config(cfg)  # graph not present; telemetry unregistered → no raise


# --- full CLI subprocess e2e: the real `agentforge` binary --------


def _agentforge_bin() -> str | None:
    """The installed `agentforge` console script next to this interpreter."""
    candidate = Path(sys.executable).parent / "agentforge"
    if candidate.exists():
        return str(candidate)
    return shutil.which("agentforge")


def _run_validate(site: Path, yaml_path: Path) -> subprocess.CompletedProcess[str]:
    """Run `agentforge config validate` in a real subprocess with the
    fake distribution discoverable via PYTHONPATH (so the child's own
    `importlib.metadata` finds the entry point — no in-process state)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(site), *([p] if (p := env.get("PYTHONPATH")) else [])])
    return subprocess.run(  # nosec B603 — fixed argv, no shell
        [_agentforge_bin() or "agentforge", "config", "validate", "--path", str(yaml_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.skipif(_agentforge_bin() is None, reason="agentforge console script not installed")
def test_cli_subprocess_validates_registered_section(tmp_path: Path) -> None:
    """End-to-end: the real `agentforge` binary discovers a real installed
    `agentforge.config_sections` entry point and validates `app.graph`."""
    site = tmp_path / "site-packages"
    site.mkdir()
    _install_fake_dist(site)
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("app:\n  graph:\n    store:\n      path: .ckg\n    max_hops: 4\n")

    result = _run_validate(site, yaml_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "OK" in result.stdout


@pytest.mark.skipif(_agentforge_bin() is None, reason="agentforge console script not installed")
def test_cli_subprocess_rejects_section_typo(tmp_path: Path) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    _install_fake_dist(site)
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("app:\n  graph:\n    store:\n      path: .ckg\n    max_hopz: 4\n")

    result = _run_validate(site, yaml_path)
    assert result.returncode == 1
    assert "app.graph" in result.stderr
