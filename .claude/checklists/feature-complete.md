# Feature-complete checklist (definition of done)

After PR is approved and merged. The feature is **shipped** when every
box is checked. Skipping items leaves the framework in an inconsistent
state.

## Merge

- [ ] PR approved by reviewer (or by user during solo work).
- [ ] CI green.
- [ ] **Squash-merged** to main (per `.claude/standards/git.md`).
- [ ] Squashed commit message uses the PR title as subject and a clean
      rollup as body.
- [ ] Feature branch deleted on origin (`gh pr merge --delete-branch`).
- [ ] Local feature branch deleted: `git branch -D feat/NNN-slug`.

## Sync

- [ ] Switched to main: `git checkout main`.
- [ ] Pulled: `git pull --ff-only`.
- [ ] Latest main contains the squash-merge commit.

## Update feature catalogue and doc

- [ ] In `docs/features/feat-NNN-*.md`:
  - Status: `shipped`
  - Add a "Shipped in" line to metadata (e.g. `**Shipped in**: 0.2.0`)
- [ ] In `docs/features/README.md` catalogue:
  - Status column updated to `shipped`
  - Target version column reflects the actual ship version

## Update state

- [ ] `.claude/state/current.md`:
  - feature: `(none)`
  - state: `idle`
  - last_shipped: `feat-NNN @ <commit-sha>`
  - last_shipped_at: `<YYYY-MM-DDTHH:MM>`
- [ ] `.claude/state/log.md` appended:
  - `## YYYY-MM-DD — feat-NNN shipped`
  - Commit SHA on main
  - Brief summary (1-2 lines)
  - Bug carries that landed in this feature: list of `[BUG-CARRIED]`
    items from the development log

## Update propagation

- [ ] If this feature changed a contract used by other features, those
      features' docs are updated to reference it.
- [ ] If this feature added a new module, the architecture.md module
      catalogue lists it.
- [ ] If this feature added a new ABC, the design-principles.md
      examples are updated if relevant.
- [ ] If this feature changed the AGENTS.md anti-pattern list, the
      AGENTS.md template in `agentforge-templates` is updated.

## Release notes (when applicable)

- [ ] If a release is being cut as a result of this feature
      (e.g. completing the 0.1 critical path), a release note is added
      to `docs/releases/<version>.md`.
- [ ] CHANGELOG.md (when it exists) entry added.

## Bug carries reconciliation

If any `[BUG-CARRIED]` entries landed in this feature:

- [ ] Each is listed in the feature doc's "Notable fixes" section
      (added if not present).
- [ ] If the bug exposed a gap in another feature's design, a comment
      in that other feature's doc references the fix.

## State integrity

- [ ] `python scripts/check_state_updated.py` passes.
- [ ] `python scripts/check_doc_links.py` passes.
- [ ] `python scripts/check_feature_docs.py` passes.
- [ ] `python scripts/check_adrs.py` passes.

## Ready for next feature

- [ ] Picked the next eligible feature per `.claude/checklists/pre-feature.md`.
- [ ] Or, if the project is idle (no eligible features), `state/current.md`
      reflects `state: idle` until the user directs further work.
