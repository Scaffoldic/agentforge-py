# Documentation Standards

Documentation is part of the contract. A code change without a doc
change is incomplete.

## What every feature requires

Every feature must, in the same PR, ship updated:

1. **Feature doc** at `docs/features/feat-NNN-*.md` — Status field
   advanced through `proposed → accepted → in-progress → shipped`.
2. **AGENTS.md** at repo root — if the feature changes a convention or
   adds an anti-pattern that an AI assistant should avoid.
3. **Runbook entry** under `docs/runbooks/...` (in
   `agentforge-templates`) — if the feature is user-facing (every
   feature with `Languages: both` or that adds a config knob).
4. **ADR** at `docs/adr/NNNN-*.md` — if the change makes a load-bearing
   architectural decision (a new ABC, a new contract, a different
   approach to a previously-decided concern).

## Feature docs

- Use the template: `.claude/templates/feature.md`.
- Lead with the three "why" sections: 1) Why this feature, 2) Why it
  must ship as framework, 3) How derived agents benefit. If you cannot
  write those crisply, the feature is not ready.
- Code blocks must be runnable (modulo imports) — no pseudocode in §4.1.
- **Status discipline** —
  - `proposed`: doc exists, design under discussion
  - `accepted`: design locked, ready to implement
  - `in-progress`: branch exists, work underway
  - `shipped`: merged, version recorded in metadata
  - `deferred` / `dropped`: kept for history with reason
- Every linked feat-NNN / ADR-NNNN reference must resolve.

## ADRs

- Use the template: `.claude/templates/adr.md`.
- MADR / Nygard format.
- **Numbers immutable.** Once assigned, never reused.
- Superseded ADRs stay in place: status becomes `Superseded by ADR-NNNN`;
  body untouched.
- Every ADR has at least 3 considered options (including the do-nothing
  option where applicable).
- Decision drivers must be specific and verifiable.

## Design docs

- Use the template: `.claude/templates/design.md`.
- Cross-cutting designs that span more than one feature.
- Architecture docs (steady-state shape) use the architecture template
  instead.

## Runbooks

(Authored in `agentforge-templates` repo; rendered into generated
projects per feat-019.)

- Format: 5-line TL;DR, numbered steps, troubleshooting table, related
  runbooks.
- Each runbook has a marker header and a fenced custom section
  (`<!-- agentforge:custom -->`) so developer customisation survives
  upgrades.

## Cross-references

- **Always link by relative path** — `[`feat-001`](./feat-001-...)`,
  not bare text.
- Feature docs link to: their ADRs, related features, design docs,
  archived predecessors.
- ADRs link to: related ADRs, supporting feature docs, external prior
  art.

## What NOT to write

- **Documentation files outside the structure.** No
  `docs/random-notes.md`. Everything has a place.
- **Plans / decision logs** during a session. Use `.claude/state/` for
  intra-session tracking; commit only finalised decisions to
  `docs/`.
- **Auto-generated API reference** — handled at the framework's docs
  site, not in this repo.
- **Tutorials** — those are runbooks (in `agentforge-templates`).

## Markdown conventions

- ATX headings (`# Heading`, `## Subheading`).
- Lists: `-` for unordered, `1.` for ordered.
- Code blocks always specify the language: ` ```python `, ` ```yaml `.
- Tables for tabular data; not nested lists pretending to be tables.
- Hard wrap at ~80 columns where reasonable; tables and code unbroken.

## Required references in every doc

Every feature / design / ADR doc concludes with a `References` section
linking the most relevant siblings. The framework's reference graph is
load-bearing — broken links are a CI failure (per pre-commit
`scripts/check_doc_links.py`).

## Pre-commit checks for docs

- `scripts/check_feature_docs.py` — every doc under `docs/features/`
  matches the template structure (required headings present).
- `scripts/check_adrs.py` — every ADR is numbered correctly, no
  duplicates, status field valid.
- `scripts/check_doc_links.py` — every relative link inside `docs/`
  resolves to an existing file or anchor.
- Markdown lint via `ruff` / `markdownlint`.

## References

- [`.claude/templates/`](../../.claude/templates/) — every doc template
- [`docs/README.md`](../../docs/README.md) — public docs entry point
- [`docs/adr/README.md`](../../docs/adr/README.md) — ADR process
