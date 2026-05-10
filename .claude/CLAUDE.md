# CLAUDE.md — agentforge-py

> This file is `agentforge-py`'s entry point for AI assistants
> (Claude Code and any other tool that reads CLAUDE.md or AGENTS.md).
> Everything you need to work on this project is **inside this
> repo**. The reading order below references **only** files in
> `agentforge-py/` — no upward path traversal.

## Read first, in order

1. [`AGENTS.md`](../AGENTS.md) — universal AI-assistant rules for
   this project (workflow, branch naming, anti-patterns, the
   workspace's nine project-level rules)
2. [`.claude/state/current.md`](./state/current.md) — what feature
   is in progress, what branch we're on, what's done, what's pending
3. [`.claude/state/README.md`](./state/README.md) — how the state
   files are written and read
4. [`docs/features/README.md`](../docs/features/README.md) —
   catalogue of every canonical feat-NNN spec
5. [`docs/features/feat-NNN-*.md`](../docs/features/) — the active
   feature's spec (linked from `state/current.md`)
6. [`docs/design/`](../docs/design/) — architecture, design
   principles, module-system, persistence-and-orm, scaffolding —
   the framework's load-bearing decisions
7. [`docs/adr/`](../docs/adr/) — immutable architectural decision
   records (MADR / Nygard format)
8. [`.claude/standards/`](./standards/) — coding / testing / git /
   docs / configuration standards
9. [`.claude/checklists/`](./checklists/) — pre-feature, pre-commit,
   pre-pr, feature-complete checklists
10. [`docs/roadmap.md`](../docs/roadmap.md) — shipped + backlog
    pointer (canonical numbering)
11. [`CHANGELOG.md`](../CHANGELOG.md) — release notes

## Project-specific rules

These extend the universal rules in `AGENTS.md`. Where the two
overlap, **AGENTS.md is authoritative**.

- **Use TaskCreate / TaskUpdate** to track per-feature progress in
  addition to updating `.claude/state/current.md`. The state file
  is the durable record across sessions; tasks are the in-session
  view.
- **Use Plan mode** for design analysis at the start of each
  feature. Exit plan mode only when the design is approved by the
  user.
- **Use parallel tool calls** wherever the operations are
  independent. Especially: parallel writes for the multiple files
  a single feature touches.
- **Do not use Bash for `find`, `grep`, `cat`, or `sed`** — use the
  dedicated tools (`Glob`, `Grep`, `Read`, `Edit`).
- **Never bypass pre-commit with `--no-verify`** unless the user
  explicitly authorises it for a specific commit. The hook is the
  enforcement of `AGENTS.md` rules 5 / 7 / 8.

## Feature numbering — read this before opening a `feat/<NNN>-*` branch

- The canonical feature catalogue is `docs/features/README.md`.
  **Branch number `<NNN>` MUST match an existing
  `docs/features/feat-NNN-*.md` spec.** No invented numbers.
- If you can't find a canonical spec for the work, the work
  doesn't have a feat-NNN number — use `chore/`, `docs/`, or
  `fix/` prefix instead, or write a spec first.
- **Every feature PR updates the matching spec's `Implementation
  status` section** before merge. The spec is the durable record
  of what shipped, what was deferred, and any deviations from the
  design. CHANGELOG is the user-facing summary; the spec is the
  developer-facing one. Both ship in the same PR.

## Why this project is self-contained

The parent workspace at
`/Users/khemchandjoshi/MbytesWorkspace/ai-agents/` hosts
**meta-level** material — universal pipeline, design principles,
ADRs that span Python and TypeScript implementations. The reverse
isn't true: project-specific work (feature specs for v0.1
implementation, per-project state, CHANGELOG, etc.) lives **inside
each project** so each project's CLAUDE.md / AGENTS.md / pipeline
forms a complete loop without crossing the workspace boundary.

This avoids two failure modes that bit feat-005 (see
`state/log.md` 2026-05-10 entries):

1. AI sessions traversing upward and finding stale or empty
   files (the parent's `.claude/state/current.md` had been
   abandoned mid-feat-002).
2. AI sessions invented feat-NNN numbers from CHANGELOG memory
   when the canonical catalogue wasn't accessible from the project
   directory.

A new contributor cloning just `agentforge-py` should be able to
work without reading anything outside it. Cross-project
architecture / ADR context is available at parent workspace level
when needed for context, but it's never on the critical path for
project-specific work.
