# enh-006: Upgrade drift report — surface which workarounds a bump made removable

> Improves a *shipped* feature (feat-011, scaffolding-and-upgrade). Filed
> as issue [#115](https://github.com/Scaffoldic/agentforge-py/issues/115)
> by a consumer agent (`agentforge-graph`) building on agentforge-py.
> Not a defect — the version bump works — this adds the missing *signal*
> that tells a consumer which of their framework workarounds a bump just
> made removable. Sibling of [bug-025](../bugs/bug-025-upgrade-overwrites-forked-and-custom.md)
> (the `agentforge upgrade` data-loss fix), filed together.

---

## Metadata

| Field | Value |
|---|---|
| **ID** | enh-006 |
| **Title** | Upgrade drift report (`agentforge upgrade --notes` + deprecation registry) |
| **Status** | `proposed` |
| **Owner** | kjoshi |
| **Created** | 2026-06-22 |
| **Target version** | 0.4 |
| **Languages** | `python` |
| **Improves** | feat-011 (scaffolding-and-upgrade) |

---

## 1. Summary

After a consumer bumps their `agentforge-py` pin, nothing tells them
*"these two things you worked around upstream are now fixed — delete your
workarounds."* This enhancement gives the framework a **drift report**:

1. **CHANGELOG issue traceability** — every entry that resolves a tracked
   issue ends with `(closes #NN)`, so the slice between two pins answers
   "which of my filed issues does this version fix?" *(Shipped already in
   bug-025 / PR #116; recorded here as part 1 because it's the floor of
   this enhancement and the rest builds on it.)*
2. **`agentforge upgrade --notes [<from>..<to>]`** (and an end-of-upgrade
   summary) — prints the CHANGELOG slice + active deprecations between two
   versions, offline, from data shipped in the wheel.
3. **A deprecation registry** — superseded seams emit a `DeprecationWarning`
   naming the replacement API, and that same registry feeds the notes
   report so a consumer sees retired workarounds without reading source.

## 2. Motivation

A disciplined consumer logs every framework workaround against a baseline
version, intending to remove it once the framework fixes it upstream. But
the cleanup is easy to miss: bumping the pin and running the test suite
verifies *"nothing broke"* (compatibility) — nothing reports *"these
seams changed; your workarounds are now dead code."*

Concretely, the reporter's 0.2.4 → 0.3.x bump silently retired two
workarounds, discovered only by re-reading framework source:

- the strict config validator began accepting an `app:` passthrough
  (enh-002) — they had kept a whole second config file to avoid it;
- `MCPServer.from_http` grew a `middleware=` hook (enh-003) — they had
  re-implemented ~60 lines of HTTP-serve internals to add auth.

Both shipped in 0.3.x. A consumer without re-reading discipline keeps the
dead workarounds indefinitely. The framework already *has* the
information (CHANGELOG, the enh/bug specs); it just never surfaces it at
the one moment a consumer needs it — right after the bump.

## 2.5 Framework-level vs derived-agent-level

**Framework.** The data a drift report needs — the CHANGELOG, the
`(closes #NN)` mapping, the set of deprecated seams and their
replacements — lives in the framework package and changes every release.
A consumer cannot derive *"which of my filed issues this version fixed"*
or *"which seam I worked around is now deprecated"* from their own agent
code; only the framework knows what it changed.

- **Derived-agent test:** the workaround (a human re-reading framework
  source after every bump, or hand-maintaining a per-version "what got
  fixed" list) re-derives information the framework owns and must track
  it across versions — fails the test → framework work.
- **How it helps derived agents:** a consumer runs one command after
  bumping the pin and gets the list of resolved issues + retired seams
  for the exact version range — no source reading, no guesswork. Every
  org agent on the framework benefits identically; nothing here is
  specific to one agent's domain.

## 3. Before / after

| Aspect | Before | After |
|---|---|---|
| "Which of my issues did this bump fix?" | re-read framework source / CHANGELOG by hand | `grep '(closes #'` the range, or `agentforge upgrade --notes` |
| "Which seams I worked around changed?" | discovered by accident, months later | listed in the drift report; `DeprecationWarning` at runtime |
| Notes available offline | no (CHANGELOG is a GitHub URL, not in the wheel) | yes — notes data ships in the package |
| After a normal `agentforge upgrade` | one-line "complete" | + a drift summary for the version range upgraded |

```console
$ agentforge upgrade --notes
  → drift from 0.2.4 → 0.3.1 (your scaffold pin → installed):

  Fixed (resolves issues you may have filed/worked around):
    - enh-002  config validator accepts `app:` passthrough        (closes #86)
    - enh-003  MCPServer.from_http(middleware=…) auth seam         (closes #93)
    - bug-025  upgrade no longer clobbers forked/custom files      (closes #114)

  Deprecated (workarounds you can retire):
    - MCPServer.from_http(runner=…) for auth → use middleware=     (since 0.3.0)

  3 fixes, 1 deprecation in this range.
```

## 4. Design

### 4.1 Shipping notes offline (the load-bearing decision)

`agentforge upgrade --notes` must work **offline** (per the framework's
offline-determinism principle) and against the *installed* version, so it
cannot fetch from GitHub. Today the wheel does **not** ship `CHANGELOG.md`
(`packages/agentforge/pyproject.toml` sets `readme = "README.md"`; the
changelog is only a `[project.urls]` link). Two options:

- **(A) Force-include `CHANGELOG.md` in the wheel** and parse the
  Keep-a-Changelog format (`## [x.y.z]` headers, `### Fixed` blocks,
  `(closes #NN)` tails) at runtime.
- **(B) Generate a structured `agentforge/_notes/changelog.json`** at
  build time from `CHANGELOG.md` (version → {fixed, deprecated, closes}).

**Recommendation: (B).** A parser over free-form markdown is fragile and
re-runs on every invocation; a build-time structured artifact is parsed
once into a stable schema, is trivially version-sliceable, and keeps the
deprecation registry (4.3) in the same shape. (A) is the cheaper fallback
if we want zero build tooling. Either way the `(closes #NN)` convention
(part 1) is the parse anchor.

### 4.2 Version range defaults

The "from" version is already recorded: the managed-files lock entries
carry `source_version`, and `answers.yml` carries `_template_version` —
the framework version at the consumer's last scaffold/upgrade. The "to"
is the installed framework version (`version("agentforge-py")`). So:

- `agentforge upgrade --notes` (no arg) → from = lock version, to =
  installed.
- `agentforge upgrade --notes 0.2.4..0.3.1` → explicit range.
- A drift summary also prints automatically at the **end of a normal
  `agentforge upgrade`**, for the range it just moved across — the single
  most useful moment.

Open question (§7): standalone `agentforge notes` / `agentforge doctor`
vs. only the `upgrade --notes` flag. Leaning `upgrade --notes` + the
auto-summary to keep the command surface small; a `doctor` umbrella can
absorb it later.

### 4.3 Deprecation registry (part 3)

A single source of truth for retired seams:

```python
@deprecated(since="0.3.0", replacement="MCPServer.from_http(middleware=…)",
            ref="enh-003")
def _legacy_auth_runner_seam(...): ...
```

The `@deprecated` decorator (a) emits `warnings.warn(..., DeprecationWarning)`
at runtime naming the replacement, and (b) registers the entry in a
module-level table the notes report reads. `DeprecationWarning` is silent
by default for end users but visible under `-W` / pytest, so it's
non-breaking. The registry — not scraped warnings — is what the offline
notes command lists, so it works without exercising the deprecated path.

## 5. Backward compatibility

Fully additive.

- Part 1 (`closes #NN`) is a docs convention — already shipped.
- `--notes` is a new flag + new auto-summary output; no change to what
  `upgrade` writes.
- `DeprecationWarning`s are non-fatal by default; consumers who run
  `filterwarnings=error` opt into seeing them (which is the point).
- Packaging `CHANGELOG.md` / a notes artifact only *adds* a file to the
  wheel.

## 6. Implementation sketch

- `packages/agentforge/pyproject.toml`: ship the notes artifact (4.1).
- `agentforge/cli/_notes.py`: load the notes artifact, slice by
  `from..to`, merge in the deprecation registry, format the report.
- `agentforge/cli/upgrade_cmd.py`: add `--notes` (range optional);
  call the formatter at the end of a successful `_do_upgrade` for the
  range upgraded.
- `agentforge/_deprecation.py`: `@deprecated` decorator + registry; wire
  the first real entries (the enh-002 / enh-003 superseded seams, if any
  remain) as the seed set.
- Build step (if 4.1-B): a `scripts/` generator + a CI check that the
  structured notes match `CHANGELOG.md` (same drift-guard pattern as the
  spec-status / changelog cross-checks).

## 7. Risks / open questions

| Risk / question | Note |
|---|---|
| Markdown CHANGELOG parsing is brittle | prefer the build-time structured artifact (4.1-B); pin the format with the existing CHANGELOG drift-check |
| Command surface creep (`--notes` vs `doctor`) | start with `upgrade --notes` + auto-summary; defer a `doctor` umbrella |
| Deprecation registry drift from reality | the registry *is* the source of truth (decorator-driven), and the notes report reads it — not scraped warnings |
| "from" version missing (hand-edited state) | fall back to requiring an explicit `<from>..<to>` and printing a hint, mirroring the existing `_template_version` guards in `upgrade` |
| Sister-package versions | the train bumps all packages in lockstep (ADR-0015), so a single version range is correct for the whole install |

## 8. References

- Improved feature: feat-011 (scaffolding-and-upgrade)
- Issue: #115
- Sibling: bug-025 (upgrade data-loss) — filed together by the same consumer
- Precedent for surfaced fixes: the `(closes #NN)` convention in
  `.claude/standards/git.md` (shipped in bug-025)
- Examples of retired workarounds this would have surfaced: enh-002
  (`app:` passthrough), enh-003 (`from_http(middleware=…)`)
</content>
