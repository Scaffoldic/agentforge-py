# Scripts

Helper scripts run by `.pre-commit-config.yaml` and CI. Stub
implementations land alongside feat-001; until then, the scripts are
documented here and the pre-commit hooks reference them by name (the
hooks are no-ops when the scripts don't yet exist).

## Inventory

| Script | Purpose | Activates with |
|---|---|---|
| `check_feature_docs.py` | Verifies every doc under `docs/features/` matches the template structure (required headings present; metadata block valid) | doc phase (now) |
| `check_adrs.py` | Verifies every ADR is numbered correctly, no duplicates, status field valid, supersedes pointers resolve | doc phase (now) |
| `check_doc_links.py` | Verifies every relative link inside `docs/` and `.claude/` resolves to an existing file or anchor | doc phase (now) |
| `check_state_updated.py` | Verifies `.claude/state/current.md` and `log.md` are recent (within 24h) and `current.md > feature` matches the active git branch | doc phase (now) |
| `check_no_managed_edits.py` | Verifies no `AGENTFORGE-MANAGED` files in this repo are silently modified outside an agentforge-templates branch | doc phase (now) |
| `check_no_magic_numbers.py` | Verifies production Python code under `python/` has no magic numbers / hardcoded thresholds (per `.claude/standards/configuration.md`) | feat-001 |
| `coverage_ratchet.py` | CI-only. Compares PR coverage to main; fails if coverage regressed by > 0.5% | feat-001 |
| `testpypi_dry_run.py` | Mandatory pre-release step. Builds all 34 packages, uploads to TestPyPI in rate-limit-aware batches, smoke-installs `agentforge-py` from TestPyPI and imports `agentforge.Agent`. Driven by `playbooks/publish-to-pypi.md` §3 and `.claude/checklists/pre-release.md` §8. | v0.2.1 |

## Implementation note

The scripts are **deliberately stub-able** so the pre-commit config can
reference them today and they activate as code lands. Each script
should:

1. Exit `0` if no relevant files exist (e.g. `check_no_magic_numbers.py`
   exits 0 if `python/agentforge-py/src/` is empty).
2. Exit non-zero with a descriptive message on real failure.
3. Be runnable standalone: `python scripts/check_feature_docs.py`.

## Where these are used

- **Local pre-commit**: `.pre-commit-config.yaml` references them.
- **CI**: `.github/workflows/ci-linux.yml` runs the same checks on
  every PR (Linux only). `ci-windows.yml` and `ci-mac.yml` run the
  same suites on Windows / macOS on `workflow_dispatch`.
- **Manual**: developers can run any script directly during a session.
