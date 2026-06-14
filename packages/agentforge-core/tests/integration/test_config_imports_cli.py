"""Full CLI subprocess e2e for the `imports:` directive (feat-026
Phase 3).

The unit tests in `tests/unit/test_config_imports.py` load real files
through the loader API. These go one level further: they run the real
`agentforge config {show,validate}` binary in a subprocess against a
multi-file config, proving the directive works end-to-end through the
CLI exactly as a user invokes it.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404 — fixed argv, no shell
import sys
from pathlib import Path

import pytest
import yaml


def _agentforge_bin() -> str | None:
    candidate = Path(sys.executable).parent / "agentforge"
    if candidate.exists():
        return str(candidate)
    return shutil.which("agentforge")


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 — fixed argv, no shell
        [_agentforge_bin() or "agentforge", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=dict(os.environ),
        check=False,
    )


pytestmark = pytest.mark.skipif(
    _agentforge_bin() is None, reason="agentforge console script not installed"
)


def test_cli_show_resolved_merges_imports(tmp_path: Path) -> None:
    (tmp_path / "shared.yaml").write_text("agent:\n  model: shared-model\n  max_iterations: 9\n")
    (tmp_path / "agentforge.yaml").write_text(
        "imports:\n  - shared.yaml\nagent:\n  name: local-agent\n"
    )

    result = _run(["config", "show", "--resolved", "--path", "agentforge.yaml"], cwd=tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    parsed = yaml.safe_load(result.stdout)
    # Imported value present, local value present, directive consumed.
    assert parsed["agent"]["model"] == "shared-model"
    assert parsed["agent"]["max_iterations"] == 9
    assert parsed["agent"]["name"] == "local-agent"
    assert "imports" not in parsed


def test_cli_validate_passes_with_imports(tmp_path: Path) -> None:
    (tmp_path / "shared.yaml").write_text("agent:\n  budget:\n    usd: 3.0\n")
    (tmp_path / "agentforge.yaml").write_text("imports:\n  - shared.yaml\n")

    result = _run(["config", "validate", "--path", "agentforge.yaml"], cwd=tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "OK" in result.stdout


def test_cli_validate_fails_on_bad_imported_value(tmp_path: Path) -> None:
    """A schema violation that lives in an imported file is caught the
    same as one in the base file — imports are fully validated."""
    (tmp_path / "shared.yaml").write_text("agent:\n  budget:\n    usd: -5\n")  # negative
    (tmp_path / "agentforge.yaml").write_text("imports:\n  - shared.yaml\n")

    result = _run(["config", "validate", "--path", "agentforge.yaml"], cwd=tmp_path)
    assert result.returncode == 1
    assert "agent.budget.usd" in result.stderr


def test_cli_validate_reports_missing_import(tmp_path: Path) -> None:
    (tmp_path / "agentforge.yaml").write_text("imports:\n  - nope.yaml\n")
    result = _run(["config", "validate", "--path", "agentforge.yaml"], cwd=tmp_path)
    assert result.returncode == 1
    assert "not found" in result.stderr
