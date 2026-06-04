# CLAUDE.md — agentforge-py

> This file is `agentforge-py`'s entry point for AI assistants
> (Claude Code and any other tool that reads CLAUDE.md or
> AGENTS.md). The reading order below references **only** files
> inside this repo. A new contributor cloning `agentforge-py`
> standalone (without any parent workspace) has everything they
> need to work on the project.

## Read first, in order

1. [`AGENTS.md`](../AGENTS.md) — project rules (workflow, branch
   naming, hard rules, anti-patterns, pre-commit, CI). This is the
   self-contained workflow document for the project.
2. `.claude/state/current.md` — what feature is in progress, what
   branch we're on, what's done, what's pending. **Local-only,
   git-ignored** (per-session working state, not published). May be
   absent on a fresh clone — that's expected; create it when you
   start tracking work. The write/read format is described in
   `.claude/state/README.md` (also local-only).
3. [`docs/features/README.md`](../docs/features/README.md) —
   catalogue of every canonical feat-NNN spec.
4. [`docs/features/feat-NNN-*.md`](../docs/features/) — the active
   feature's spec (linked from `state/current.md`).
5. [`docs/design/`](../docs/design/) — architecture, design
   principles, module-system, persistence-and-orm, scaffolding —
   the framework's load-bearing decisions.
6. [`docs/adr/`](../docs/adr/) — immutable architectural decision
   records (MADR / Nygard format).
7. [`.claude/standards/`](./standards/) — coding / testing / git /
   docs / configuration standards.
8. [`.claude/checklists/`](./checklists/) — pre-feature,
   pre-commit, pre-pr, feature-complete checklists.
9. [`docs/roadmap.md`](../docs/roadmap.md) — shipped + backlog
   pointer (canonical numbering).
10. [`CHANGELOG.md`](../CHANGELOG.md) — release notes.

## Project-specific Claude Code notes

These extend the rules in `AGENTS.md`. Where the two overlap,
`AGENTS.md` is authoritative.

- **Use TaskCreate / TaskUpdate** to track per-feature progress
  in addition to updating `.claude/state/current.md`. State file
  is the durable record across sessions; tasks are the in-session
  view.
- **Use Plan mode** for design analysis at the start of each
  feature. Exit plan mode only when the design is approved by the
  user.
- **Use parallel tool calls** wherever the operations are
  independent. Especially: parallel writes for the multiple files
  a single feature touches.
- **Do not use Bash for `find`, `grep`, `cat`, or `sed`** — use
  the dedicated tools (`Glob`, `Grep`, `Read`, `Edit`).
- **Never bypass pre-commit with `--no-verify`** unless the user
  explicitly authorises it for a specific commit.

## Feature numbering — read this before opening a `feat/<NNN>-*` branch

- The canonical feature catalogue is `docs/features/README.md`.
  **Branch number `<NNN>` MUST match an existing
  `docs/features/feat-NNN-*.md` spec.** No invented numbers.
- If you can't find a canonical spec for the work, it's not a
  feature — use `chore/`, `docs/`, or `fix/` prefix instead, or
  write a spec first.
- **Every feature PR updates the matching spec's `Implementation
  status` section** before merge. The spec is the durable
  record of what shipped, what was deferred, and any deviations
  from the design. CHANGELOG is the user-facing summary; the
  spec is the developer-facing one. Both ship in the same PR.

## Why this project is self-contained

`agentforge-py` is open source. External contributors clone it
standalone — they never see any parent directory. So everything
needed to contribute lives inside this repo: workflow rules
(`AGENTS.md`), feature specs (`docs/features/`), design and
architecture (`docs/design/`, `docs/adr/`), state tracking
(`.claude/state/`), standards and checklists
(`.claude/standards/`, `.claude/checklists/`), the roadmap, and
the changelog.

This avoids two failure modes that bit feat-005 (see
`state/log.md` 2026-05-10 entries):

1. AI sessions traversing upward and finding stale or empty
   files (an earlier shared parent layout had abandoned state
   files mid-feature).
2. AI sessions inventing feat-NNN numbers from CHANGELOG memory
   when the canonical catalogue wasn't accessible from the
   project directory.

A new contributor cloning just `agentforge-py` should be able to
work on it without reading anything outside it.
