# 15 — Upgrade your agent

> **Goal:** pull the latest framework changes into this project
> without losing your customisations.
> **Time:** ~15 minutes.
> **Prereqs:** runbook 01.

## TL;DR

```bash
agentforge upgrade --dry-run     # preview
agentforge upgrade               # apply
agentforge status                # any drift?
pytest -q
```

## Step by step

1. **Read the framework's CHANGELOG.** Open
   `docs/features/README.md` from the framework repo (or the
   release notes) and skim what shipped between your version
   and current.
2. **Stage clean.** Commit any uncommitted work first.
   `agentforge upgrade` is a three-way merge — easier to
   resolve from a clean tree.
3. **Dry-run.** `agentforge upgrade --dry-run` prints the diff
   without writing. Use to scope the review.
4. **Apply.** `agentforge upgrade` runs Copier's `run_update`,
   merging managed files against the recorded template
   version. Custom sections of three-section docs are
   preserved automatically; non-managed code is left alone.
5. **Resolve conflicts.** Copier surfaces conflicts in `.rej`
   files. Edit by hand or `agentforge fork <path>` to claim
   the file outright (future upgrades skip it).
6. **Verify.** `agentforge status` should show no `DRIFTED`
   files; `pytest -q` should pass.

## Variations

- **Fork a file.** `agentforge fork src/myagent/agent_runtime.py`
  strips the marker and flips the lock entry to `forked: true`.
  Future upgrades skip it.
- **Unfork.** `agentforge unfork <path>` re-prepends the marker;
  next upgrade re-pulls framework content (lossy).
- **Pin a target ref.** `agentforge upgrade --to <ref>` points
  at a specific template ref instead of the latest. Useful for
  staged rollouts.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No .agentforge-state/answers.yml` | this directory wasn't scaffolded by `agentforge new` | upgrade only works on scaffolded projects |
| `.rej` conflict file | three-way merge couldn't auto-resolve | edit by hand; the `.rej` carries the framework's preferred shape |
| Custom section in runbook overwritten | edit went above the `<!-- agentforge:end-managed -->` marker | move custom content below the marker, restore from git |
| DB schema out of date | driver bumped its schema | `agentforge db backup` → `agentforge db migrate` → `agentforge db restore` |

## Related

- Runbook 08 — Add memory (db migrate during upgrade)
- Runbook 14 — Deploy your agent (release process)
- Feature spec: `docs/features/feat-011-scaffolding-and-upgrade.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
