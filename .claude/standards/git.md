# Git Standards

Branch / commit / PR conventions. One feature = one branch = one PR.

## Branch naming

| Branch type | Pattern | When |
|---|---|---|
| Feature | `feat/NNN-slug` | Active feature work (v0.x and beyond) |
| Bug | `bug/NNN-slug` | **v1.0+ only.** During v0.x, all fixes go on the active feature branch. |
| Enhancement | `enh/NNN-slug` | **v1.0+ only.** Same. |
| Docs-only | `docs/<area>` | Docs-only changes that don't fit a feature (rare; tracker entry required) |
| Chore | `chore/<area>` | Tooling, CI, dependencies (rare; logged in `state/log.md`) |

`NNN` is the feature/bug/enh number. `slug` is hyphenated lowercase (e.g.
`feat/001-core-contracts-and-agent`).

`main` is always green. No direct commits to main; everything via PR.

## Commit messages

[**Conventional Commits**](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body — optional, wrap at 72>

<footer — optional>
```

| Type | Use |
|---|---|
| `feat` | New feature or contract; ships in a feat-NNN branch |
| `fix` | Bug fix on the active feature branch (during v0.x) or in a `bug/NNN-*` branch (v1.0+) |
| `docs` | Documentation changes only |
| `test` | Test changes only |
| `refactor` | Behaviour-preserving change |
| `chore` | Tooling, CI, deps |
| `perf` | Performance improvement |
| `revert` | Reverts an earlier commit |

**Scope** is the feature id or area: `feat(feat-001)`, `fix(feat-005)`,
`docs(adr-0021)`, `chore(ci)`.

**Subject** is imperative, present tense, ≤ 72 chars, no trailing period:
- ✅ `feat(feat-003): add capability negotiation to LLMClient`
- ❌ `Added a capability method.`

**Body** explains *why* the change was made (the *what* is in the
diff). Wrap at 72 columns. Reference design principles or ADRs:

```
feat(feat-003): add capability negotiation to LLMClient

LLMClient ABC was returning the lowest-common-denominator surface,
making caching/thinking/streaming unreachable to consumers.

Per ADR-0009, capabilities are now declared via capabilities() and
consumers branch on supports("caching") before calling the optional
methods.

Refs: feat-003
```

**Footer** for breaking changes, refs:
```
BREAKING CHANGE: LLMClient.capabilities now returns set[str] instead of list[str]
Refs: feat-003, ADR-0009
```

## Per-commit hygiene

- One coherent unit of work per commit. Not "WIP commits".
- Each commit must build cleanly and tests must pass (pre-commit
  enforces).
- **Never** `git commit -am` blindly — review the diff first.
- **Never** include unrelated changes in a commit. Stash or split.

## Per-feature hygiene

- One feature = one branch = one PR.
- If a refactor unrelated to the feature is needed, raise a separate
  `refactor:` PR first; merge; rebase the feature branch onto main.
- Keep the branch up to date: `git rebase origin/main` (not `merge`).
- Before opening PR: interactive rebase to clean history (drop
  noise commits, reword sloppy messages).

## Pull requests

PR title:

```
feat-NNN: <feature title>
```

PR body uses the template in `.github/pull_request_template.md` (lands
when feat-001 ships) or, until then, the inline template in
`.claude/development-pipeline.md` §9.

Required PR contents:

- Summary (one paragraph)
- Feature reference (`Closes feat-NNN`)
- Design principles cited (which P# from the 12, which ADRs)
- Test counts (unit / integration / conformance)
- Coverage on diff (≥ 90% required)
- Bugs carried section (per pipeline §5; "None" if no fix-while-feature)
- Pre-commit hook output (✅ all green)

## Changelog — issue traceability

`CHANGELOG.md` is the user-facing record; a downstream consumer reads
the slice between their old and new pin to learn what changed. To make
that slice answer **"which of my filed issues does this version
resolve?"** without re-reading source (issue #115):

- **Every entry that closes a tracked GitHub issue ends with
  `(closes #NN)`.** Multiple: `(closes #114, #116)`.
- Entries that fix a catalogued framework bug/enh keep the
  `bug-NNN` / `enh-NNN` reference in the lead, *and* add `(closes #NN)`
  when an issue tracks it.
- A consumer who worked around a now-fixed seam can `grep '(closes #'`
  the `[Unreleased]`→latest range and see exactly which workarounds are
  safe to delete.

Example:

```
### Fixed

- **bug-025 (P1) — `agentforge upgrade` overwrote forked files…** …
  (closes #114)
```

## Merging

- **Squash merge** to main with the PR title as the squashed commit.
- The squashed commit message body should be a clean rollup of the
  individual commits' bodies.
- Delete the feature branch after merge.
- Pull main, mark feature `shipped`, update `state/log.md`, pick next.

## Forbidden

- **Force-push to main** — never.
- **`--no-verify` on commit** — only with explicit user approval, logged.
- **Mixing features in one PR** — split.
- **Editing main directly** — always via PR.
- **Merging without green CI** — never. (Even with reviewer approval.)
- **Editing a managed file in `agentforge-templates`** outside an
  agentforge-templates branch — that repo follows the same rules.
- **Committing secrets** — pre-commit detects keys; if one slips,
  rotate immediately and history-rewrite (only if not yet pushed).

## Tagging & releases

AgentForge ships under a **coordinated release train** per
[ADR-0015](../../docs/adr/0015-coordinated-release-train.md):
every framework release (`vX.Y.Z`) bumps every in-scope
workspace package to the same minor in lockstep. Patch
releases between trains are bug fixes only.

### Rules

- **Every `vX.Y.Z` tag REQUIRES release notes.** Notes live at
  `docs/releases/vX.Y.Z.md`, generated from the template at
  [`.claude/templates/release-notes.md`](../templates/release-notes.md).
  The GitHub Release body is the rendered file (`gh release
  create --notes-file …`).
- **Every tag follows the pre-release checklist** at
  [`.claude/checklists/pre-release.md`](../checklists/pre-release.md).
  Skipping the checklist is forbidden — it's the only place
  the cross-cutting drift checks (CHANGELOG ↔ spec status ↔
  roadmap ↔ state) are enforced in one pass.
- **Tag format:** annotated tags only (`git tag -a vX.Y.Z -m
  "…"`). Never push lightweight tags.
- **Versioning:** strict SemVer ([semver.org](https://semver.org)).
  During 0.x, every minor (0.Y → 0.(Y+1)) may carry breaking
  changes; patches (0.x.y → 0.x.(y+1)) are bug fixes only.
- **No skipping versions.** The next release after `vN` is
  `v(N+1)` in the natural minor sequence. Spec metadata's
  `Target version` field is **aspirational** — it records
  when a feature was originally planned, not which tag
  actually carries it. When tag cadence and original target
  diverge, the tag wins.
- **Release-notes format:** Keep a Changelog v1.1 section
  vocabulary (`Added` / `Changed` / `Deprecated` / `Removed`
  / `Fixed` / `Security`) under curated highlights up top.
- **Coordinated train table required:** every release notes
  page lists every workspace package and the version it went
  to in this train. Missing rows are a release blocker.
- **Cross-language status block required:** state Python /
  TypeScript readiness explicitly per
  [ADR-0002](../../docs/adr/0002-multi-language-python-typescript.md)
  — "Python ships first during 0.x; TS catches up to parity
  by 0.4."

### Workflow

1. Open a `chore/release-vX.Y.Z` branch off green `main`.
2. Bump every package's `pyproject.toml` version.
3. Run [`.claude/checklists/pre-release.md`](../checklists/pre-release.md)
   end-to-end.
4. Fill `docs/releases/vX.Y.Z.md` from the template.
5. Update `CHANGELOG.md` (rename `[Unreleased]` → `[X.Y.Z]
   — YYYY-MM-DD`; add a fresh empty `[Unreleased]`).
6. PR through the normal gate. Squash-merge.
7. Pull main; tag; push; create GitHub Release.

## Git hygiene tools

- **Pre-commit** runs the full check suite (see
  `.claude/standards/testing.md`).
- **Commit-msg hook** validates Conventional Commits format.
- **`gh pr create`** is the standard PR-raising path.
- **`gh release create vX.Y.Z --notes-file docs/releases/vX.Y.Z.md`**
  is the standard publish path.

## Multi-author commits

- The user is the primary author.
- Claude / AI assistance is recorded via `Co-Authored-By:` trailer:
  ```
  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  ```
- Never claim sole authorship for AI-assisted work.

## References

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Keep a Changelog v1.1](https://keepachangelog.com/en/1.1.0/)
- [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
- [`.claude/development-pipeline.md`](../development-pipeline.md)
- [`.claude/checklists/pre-commit.md`](../checklists/pre-commit.md)
- [`.claude/checklists/pre-pr.md`](../checklists/pre-pr.md)
- [`.claude/checklists/pre-release.md`](../checklists/pre-release.md)
- [`.claude/templates/release-notes.md`](../templates/release-notes.md)
- [ADR-0015 — Coordinated release train](../../docs/adr/0015-coordinated-release-train.md)
- [ADR-0007 — Locked ABC versioning](../../docs/adr/0007-locked-abc-versioning.md)
