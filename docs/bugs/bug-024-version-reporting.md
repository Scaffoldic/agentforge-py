---
status: fixed in 0.3.1
severity: P3
found-in: 0.3.0
found-via: dogfooding (post-release E2E of the published 0.3.0 wheel)
---

# bug-024 — `agentforge --version` reports `0.0.0+unknown`; `__version__` hardcoded + stale

## Symptom

Against a clean PyPI install of 0.3.0:

```
$ pip install "agentforge-py==0.3.0"
$ agentforge --version
0.0.0+unknown                         # expected: 0.3.0
$ python -c "import agentforge; print(agentforge.__version__)"
0.2.3                                 # stale
```

Every sister package was affected too (`agentforge_core.__version__`,
`agentforge_bedrock.__version__`, … all read `0.2.3`).

## Reproduction

Install any 0.3.0 wheel and run `agentforge --version` or read any
package's `__version__`.

## Root cause

Two independent defects, both "the version isn't sourced from the
distribution metadata":

1. **CLI lookup of the wrong distribution name.**
   `agentforge/cli/main.py::_resolve_version()` called `version("agentforge")`,
   but the **distribution** is `agentforge-py` (renamed in v0.2.1; the import
   package stayed `agentforge`). `version("agentforge")` raises
   `PackageNotFoundError`, so the handler returned its `0.0.0+unknown`
   fallback. So `--version` has been broken since the v0.2.1 rename.
   (`agentforge/cli/new_cmd.py` already used the correct
   `version("agentforge-py")` — with a comment about this exact trap — so
   `main.py` was simply missed.)

2. **Hardcoded `__version__` strings.** 12 packages declared
   `__version__ = "0.2.3"` as a literal. The release version-bump only edits
   `pyproject.toml [project] version`, so every `__version__` drifted away
   from the real version each release.

Surfaced by end-to-end testing the *published* 0.3.0 wheel (a fresh
`pip install` + `agentforge --version`), not the editable workspace.

## Fix

Source the version from the installed distribution metadata everywhere, so
it can never drift again:

- `main.py::_resolve_version()` → `version("agentforge-py")`.
- Every package `__init__.py` replaces the hardcoded literal with:

  ```python
  from importlib.metadata import PackageNotFoundError as _PkgNotFound  # noqa: E402
  from importlib.metadata import version as _dist_version  # noqa: E402

  try:
      __version__ = _dist_version("<distribution-name>")
  except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
      __version__ = "0.0.0+unknown"
  ```

This also removes a step from the release process: the version bump no
longer needs to touch any `__version__` (only `pyproject.toml`).

## Verification

- `packages/agentforge/tests/unit/test_cli_version.py`:
  `_resolve_version()` equals `version("agentforge-py")` and is not the
  fallback; `agentforge.__version__` equals `version("agentforge-py")`;
  `agentforge --version` exits 0 and prints the real version.
- `scripts/packaged_e2e.py::_check_version` — the wheel-level guard: against
  the freshly built+installed artifact, asserts `agentforge --version` and
  `agentforge.__version__` both equal the distribution metadata and aren't
  the `0.0.0+unknown` fallback. Catches a packaging-level regression the
  source-tree unit test can't see. Runs per-PR and in `release.yml` pre-publish.
- Manual: a clean `pip install agentforge-py==0.3.1` → `agentforge --version`
  prints `0.3.1`; `agentforge.__version__ == "0.3.1"`.
- `uv run pre-commit run --all-files` green.

## Notes

- Pre-existing since the v0.2.1 distribution rename — not a 0.3.0
  regression. Cosmetic (P3): version reporting only; no functional impact.
- Ships in 0.3.1.
