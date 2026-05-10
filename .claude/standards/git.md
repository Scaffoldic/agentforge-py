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

## Git hygiene tools

- **Pre-commit** runs the full check suite (see
  `.claude/standards/testing.md`).
- **Commit-msg hook** validates Conventional Commits format.
- **`gh pr create`** is the standard PR-raising path.

## Multi-author commits

- The user is the primary author.
- Claude / AI assistance is recorded via `Co-Authored-By:` trailer:
  ```
  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  ```
- Never claim sole authorship for AI-assisted work.

## References

- [Conventional Commits](https://www.conventionalcommits.org/)
- [`.claude/development-pipeline.md`](../development-pipeline.md)
- [`.claude/checklists/pre-commit.md`](../checklists/pre-commit.md)
- [`.claude/checklists/pre-pr.md`](../checklists/pre-pr.md)
