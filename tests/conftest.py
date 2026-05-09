"""Workspace-level pytest fixtures shared across integration / conformance.

Per `.claude/standards/testing.md`, fixtures live here so any test
under `tests/{integration,conformance,property}` can request them.
Per-package unit tests get their own conftest.py inside each package's
`tests/` directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

THIS_DIR = Path(__file__).parent
FIXTURES_DIR = THIS_DIR / "fixtures"


@pytest.fixture(scope="session")
def thresholds() -> dict[str, Any]:
    """Configurable test thresholds (timeouts, retries, expected counts).

    Per `.claude/standards/configuration.md`: tests must not hardcode
    these values. Read from `tests/fixtures/thresholds.yaml`.
    """
    path = FIXTURES_DIR / "thresholds.yaml"
    with path.open() as f:
        loaded: dict[str, Any] = yaml.safe_load(f)
    return loaded
