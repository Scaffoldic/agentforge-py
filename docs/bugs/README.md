# Bugs

Validation bugs found against shipped releases. Each `bug-NNN-*.md`
follows the format:

- Frontmatter: `status`, `severity` (P0–P3), `found-in`, `found-via`.
- Sections: Symptom · Reproduction · Root cause · Fix · Verification.

A bug closes when its fix lands on `main` and a release ships
containing it; the doc's frontmatter `status:` flips from `open` to
`fixed-in: vX.Y.Z`. Bug docs are retained as institutional memory
(so future contributors can see the same class of failure ever
happened).
