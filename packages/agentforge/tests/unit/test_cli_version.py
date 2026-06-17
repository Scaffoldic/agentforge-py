"""Regression for bug-024 — version reporting.

`agentforge --version` reported `0.0.0+unknown` (it looked up the wrong
distribution name, `agentforge` instead of `agentforge-py`), and every
package's `__version__` was a hardcoded string that drifted from
`pyproject.toml`. Both are now sourced from the installed distribution
metadata.
"""

from __future__ import annotations

from importlib.metadata import version

import agentforge
import pytest
from agentforge.cli.main import _resolve_version, main


def test_resolve_version_matches_distribution_metadata() -> None:
    """`--version` reports the real installed version, not the fallback."""
    resolved = _resolve_version()
    assert resolved == version("agentforge-py")
    assert resolved != "0.0.0+unknown"


def test_module_dunder_version_is_dynamic_and_current() -> None:
    """`agentforge.__version__` tracks the installed distribution (no longer
    a stale hardcoded literal like the pre-fix `0.2.3`)."""
    assert agentforge.__version__ == version("agentforge-py")


def test_cli_version_flag_prints_real_version(capsys: pytest.CaptureFixture[str]) -> None:
    """`agentforge --version` exits 0 and prints the real version."""
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out.strip()
    assert out == version("agentforge-py")
    assert "0.0.0+unknown" not in out
