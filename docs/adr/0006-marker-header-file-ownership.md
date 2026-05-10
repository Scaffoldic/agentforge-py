# ADR-0006: Marker-header file ownership (managed / forked / owned)

## Metadata

| Field | Value |
|---|---|
| **Number** | 0006 |
| **Title** | Marker-header file ownership (managed / forked / owned) |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | scaffolding, upgrade, ownership |

---

## 1. Context and problem statement

`agentforge upgrade` (per ADR-0005) needs to know which files in a
generated project the framework owns and may update, versus which files
the developer has authored or claimed. Without that distinction, an
upgrade either over-writes developer code or skips legitimate updates.

How do we encode file ownership inside the project itself, durably across
moves and renames, in a way that survives developer edits, formatters,
and pre-commit hooks?

## 2. Decision drivers

- Ownership state must travel *with the file*, not in an external manifest
  alone (renames must not silently lose ownership)
- Must be human-readable (developer can answer "is this mine to edit?" by
  glancing)
- Must survive code formatters
- Must work in Python, TypeScript, YAML, SQL, Markdown, and other file
  types (some of which lack `#` comments)
- A separate manifest is also needed for files that don't support inline
  comments (binaries, plain JSON)

## 3. Considered options

1. **Marker headers in source files** — first-line comment declaring
   ownership and version
2. **External manifest only** — `.agentforge-state/managed-files.yaml`
   tracks every managed path
3. **Git attributes / hooks** — `.gitattributes` rule per managed path
4. **Hybrid: headers for comment-able files + manifest for the rest**

## 4. Decision outcome

**Chosen: Option 4 — Hybrid.**

Most files (Python, TS, YAML, SQL, Markdown) get an inline marker header:

```
AGENTFORGE-MANAGED: <module>@<version> hash:<sha256-prefix>
```

Files that cannot carry comments (binary, JSON without comments) are
tracked in `.agentforge-state/managed-files.lock` instead. Both
mechanisms feed the same ownership model: each file is one of `managed`
(framework owns; upgrades touch), `forked` (developer claimed; upgrades
skip), or `owned` (developer authored; never tracked).

`agentforge fork <path>` strips the marker header, updates the lock,
and the file becomes the developer's. `agentforge unfork` reverses
(losing edits).

### Positive consequences

- Ownership visible inline — answers "can I edit this?" immediately
- Survives moves (the file carries its marker)
- Falls back to manifest for binary/JSON cases
- Hash field detects silent edits at upgrade time

### Negative consequences (trade-offs)

- Two mechanisms to keep in sync (header + lock for files that have both
  for redundancy — actually we keep them as fallbacks, not duplicates)
- Code formatters that strip leading comments would damage the marker
  (mitigated by pre-commit hook that restores it)
- Marker is one extra line at the top of every managed file

## 5. Pros and cons of the options

### Option 1: Marker headers only

- + Visible inline; survives moves
- − Doesn't work for binaries / strict-JSON

### Option 2: External manifest only

- + Works for any file type
- − Renames silently lose ownership; surprises at upgrade time
- − Developer can't tell from the file alone

### Option 3: Git attributes

- + Native git integration
- − Doesn't survive `git mv` cleanly across renames in all clients
- − Per-file ownership requires verbose attributes file

### Option 4: Hybrid (chosen)

- + Best of headers + manifest
- + Manifest acts as safety net for header-stripped files
- − Two surfaces; small complexity cost

## 6. References

- ADR-0005 (Copier scaffolding)
- [`docs/design/scaffolding-and-upgrade.md`](../design/scaffolding-and-upgrade.md) §4.4
- [`docs/features/feat-011-scaffolding-and-upgrade.md`](../features/feat-011-scaffolding-and-upgrade.md)
