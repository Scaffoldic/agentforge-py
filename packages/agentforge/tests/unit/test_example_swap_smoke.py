"""Regression guard for the public `examples/swap-by-config/` demo.

The README points new users at `examples/swap-by-config/smoke.py` as a
zero-setup proof that the install works. If a future refactor breaks that
script, this test fails before the broken example ships. It runs the example
exactly the way a user would — as a subprocess, no in-process imports — so it
catches import-path and entry-point regressions, not just logic ones.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# repo root: unit -> tests -> agentforge -> packages -> <root>
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SMOKE = _REPO_ROOT / "examples" / "swap-by-config" / "smoke.py"


def test_swap_by_config_smoke_runs_offline() -> None:
    """`smoke.py` runs the full agent loop offline and reports completion."""
    assert _SMOKE.is_file(), f"example missing: {_SMOKE}"

    proc = subprocess.run(
        [sys.executable, str(_SMOKE)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert proc.returncode == 0, f"smoke.py failed:\n{proc.stderr}"
    assert "offline agent run" in proc.stdout
    assert "finish=completed" in proc.stdout
