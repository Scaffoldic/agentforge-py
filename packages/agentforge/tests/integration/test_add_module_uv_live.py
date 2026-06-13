"""Live integration test for bug-021 — gated on `RUN_LIVE_UV=1`.

CI does not run this (it hits PyPI and spawns real `uv` subprocesses).
Local development / verification:

    RUN_LIVE_UV=1 uv run pytest \
      packages/agentforge/tests/integration/test_add_module_uv_live.py -v -m live

This is the end-to-end proof for bug-021: the unit tests in
`tests/unit/test_module_cmd.py` assert the *command* the runner builds;
this test actually runs it against a **real uv-managed venv** — the exact
environment that triggered the original "No module named pip" failure —
and confirms the install succeeds and is persisted.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path

import pytest
from agentforge.cli.module_cmd import _default_pip_runner


def _live_enabled() -> bool:
    return os.environ.get("RUN_LIVE_UV") == "1"


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not _live_enabled(), reason="RUN_LIVE_UV not set"),
    pytest.mark.skipif(shutil.which("uv") is None, reason="uv not on PATH"),
]

# A tiny, pure-Python, dependency-free distribution to install for real.
_DIST = "six"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 — fixed argv, no shell
        cmd, cwd=cwd, capture_output=True, text=True, check=True
    )


def test_add_module_runner_installs_and_persists_in_real_uv_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """bug-021 end-to-end: in a real uv-managed project (whose venv has
    no `pip` module — the original failure condition), the default runner
    installs via `uv add`, the install succeeds, and the dependency is
    persisted to `pyproject.toml` + `uv.lock` so it survives `uv sync`.
    """
    project = tmp_path / "agent"
    project.mkdir()

    # 1. Real uv-managed project + venv (standalone, not part of this repo's workspace).
    _run(["uv", "init", "--name", "agent", "--no-workspace", "--no-readme"], cwd=project)
    _run(["uv", "sync"], cwd=project)

    # 2. Establish the bug condition: the uv venv has no `pip` module, so the
    #    OLD `python -m pip` codepath would fail here with "No module named pip".
    venv_python = project / ".venv" / "bin" / "python"
    assert venv_python.exists(), "uv sync did not create the expected venv"
    pip_probe = subprocess.run(  # nosec B603
        [str(venv_python), "-m", "pip", "--version"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert pip_probe.returncode != 0, (
        f"expected the uv venv to lack a pip module (bug-021 condition); got: {pip_probe.stdout!r}"
    )

    # 3. Run the runner from inside the project. Detection finds uv.lock →
    #    uses `uv add`. This is the codepath the old `python -m pip` broke.
    monkeypatch.chdir(project)
    code = _default_pip_runner(["install", _DIST])
    assert code == 0, "uv-aware runner failed to install in a uv-managed project"

    # 4. The dependency is persisted (not an ephemeral install).
    pyproject = (project / "pyproject.toml").read_text()
    assert _DIST in pyproject, f"{_DIST} was not recorded in pyproject.toml"
    lock_after_add = (project / "uv.lock").read_text()
    assert _DIST in lock_after_add, f"{_DIST} was not recorded in uv.lock"

    # 5. It survives a subsequent `uv sync` (the trap a bare `uv pip install`
    #    would fall into — sync would uninstall an unrecorded package).
    _run(["uv", "sync"], cwd=project)
    assert _DIST in (project / "uv.lock").read_text()

    # 6. Removal path also works and de-persists the dependency.
    code = _default_pip_runner(["uninstall", "-y", _DIST])
    assert code == 0, "uv-aware runner failed to remove in a uv-managed project"
    assert _DIST not in (project / "pyproject.toml").read_text()

    # Touch sys to keep the interpreter reference meaningful in failure output.
    assert Path(sys.executable).exists()
