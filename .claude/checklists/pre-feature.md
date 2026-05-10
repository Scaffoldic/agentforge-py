# Pre-feature checklist

Before writing a single line of code on a new feature, walk this
checklist. Skipping items will cost more time later than they save now.

## Selection

- [ ] Previous feature is `shipped` (merged, main pulled, status updated).
- [ ] `.claude/state/current.md` shows `state: idle`. If not, finish or
      abandon the prior feature first.
- [ ] Selected feature has status `proposed` in
      `docs/features/README.md`.
- [ ] Every dependency listed in the feature's `Depends on:` field is
      `shipped`. If not, surface the blocker; do not work around it.

## Branch and state

- [ ] On `main`, working tree clean.
- [ ] `git pull --ff-only` succeeded.
- [ ] Created branch `feat/NNN-slug` (from feature filename).
- [ ] Updated `.claude/state/current.md`:
  - feature
  - state: `analysing`
  - started_at
  - branch
- [ ] Appended start entry to `.claude/state/log.md`.

## Reading

- [ ] Read the entire feature doc end-to-end (not skimmed).
- [ ] Read every doc in §10 References of the feature doc.
- [ ] Read every ADR cited in the feature doc.
- [ ] Read every dependency feature's doc (`Depends on:`).
- [ ] Glanced at the existing code (if any) under
      `packages/<member>/src/...` for the area touched.

## Analysis notes captured

In `.claude/state/current.md > analysis_notes:`:

- [ ] Contracts being added or extended (ABCs, types).
- [ ] Modules affected (which packages, which files).
- [ ] Existing tests requiring update (unit / integration / conformance).
- [ ] New files to create with proposed paths.
- [ ] Configuration keys added or changed.
- [ ] Ambiguities surfaced — is anything unclear in the feature doc?
      List them; ask the user before proceeding if any block design.

## Decision points flagged

- [ ] Identified any open questions in §8 of the feature doc that this
      feature must resolve.
- [ ] If the implementation forces a load-bearing decision, plan to
      write a new ADR on this branch.

## Ready to proceed

- [ ] All boxes above are checked.
- [ ] State updated to `state: designing`.
- [ ] Move on to the design stage of the pipeline.
