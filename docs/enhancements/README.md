# Enhancements

Improvements to *shipped* features (not new capabilities — those are
`feat-NNN` specs; not defects — those are `bug-NNN` docs). Each
`enh-NNN-*.md` follows the `enhancement.md` template:

- Frontmatter-style metadata: `Status`, `Severity`/`Target version`,
  `Improves` (the feat-NNN it builds on).
- A mandatory **Framework-level vs derived-agent-level** section (§2.5):
  an enhancement only belongs here if it genuinely improves framework
  code rather than something a consumer could do in their own agent.

Numbering: `enh-001`, `enh-002`, ... — never reused, never renumbered.

An enhancement closes when it lands on `main` and a release ships
containing it; `Status` flips to `shipped`.
