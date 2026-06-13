"""Shared pytest fixtures for the agentforge package's own tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_leaked_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip inherited ``GIT_*`` env vars that leak into hook runs.

    When the suite runs from a git hook (e.g. the ``pre-commit`` /
    ``pytest`` stage of ``git commit``), git exports ``GIT_DIR`` /
    ``GIT_WORK_TREE`` / ``GIT_INDEX_FILE`` pointing at the *outer*
    repository. The scaffold tests drive Copier, whose VCS detection
    (``git -C <template> rev-parse``) then resolves against that leaked
    ``GIT_DIR`` instead of the template path — Copier concludes the
    in-repo template is a git *remote* and shells out to
    ``git ls-remote <template>``, which fails (exit 128). The same tests
    pass when run outside a hook. Removing the leaked vars makes the
    tests behave identically in both environments. Tests that genuinely
    need a repo create their own with ``git init``.
    """
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(var, raising=False)
