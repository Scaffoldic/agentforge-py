# AgentForge vX.Y.Z — <release codename>

> **Template usage.** Copy this file to
> `docs/releases/vX.Y.Z.md` (create the directory on first use)
> and fill in every section before tagging. The pre-release
> checklist at `.claude/checklists/pre-release.md` walks you
> through it. The final rendered notes become the body of the
> GitHub Release attached to the `vX.Y.Z` tag.

<!-- The codename is optional but recommended; pick a memorable
     word that captures the release's theme (e.g. "Foundation",
     "Modules", "Streaming"). It shows up in announcements and
     gives consumers a quick mental anchor. -->

---

## Highlights

<!-- 3-5 visible bullets, each one or two sentences. Lead with
     what consumers can *do* now that they couldn't before. A
     code snippet of ≤ 8 lines per highlight is welcome. Use
     this section to set the headline; the per-category
     sections below cover the long tail. -->

- **`<feature title>`** — <one-sentence pitch>. <Optional 1-line
  code example showing the new surface.>
- **`<feature title>`** — <pitch>.
- **`<feature title>`** — <pitch>.

---

## What's new

<!-- Curate the user-facing changes. Pull from CHANGELOG.md but
     trim implementation chatter. Each bullet should answer "what
     can the user do differently now?", not "what did the diff
     touch?". -->

### Added

- <New public surface, new package, new CLI command. One bullet
  per locked-contract addition. Link to the canonical spec at
  `docs/features/feat-NNN-*.md` for details.>

### Changed

- <Behaviour change a consumer might notice. Note backwards
  compatibility status explicitly.>

### Deprecated

- <Symbol scheduled for removal in a later minor. Include the
  replacement and the planned removal version.>

### Removed

- <Symbol gone in this release. Should always be paired with a
  prior `Deprecated` entry in an earlier release.>

### Fixed

- <Bug fix that changes observable behaviour. Skip pure refactors
  / test-only fixes.>

### Security

- <Security-relevant changes. Always called out separately.>

---

## Breaking changes

<!-- Required section. If there are none, write "None." A 0.x →
     0.(x+1) bump may carry breaking changes per ADR-0007; a 0.x.y
     → 0.x.(y+1) patch must not. -->

**None** — or — list each breaking change with:

1. **What changed:** <one sentence>
2. **Why:** <one sentence; cite spec / ADR>
3. **Migration:** <code-level instructions>

---

## Migration guide

<!-- Only present for releases with breaking changes or
     non-trivial deprecations. Walk a consumer from the prior
     release to this one. Code snippets > prose. -->

### Upgrading from vX.(Y-1).0

```diff
- from agentforge.old_path import OldName
+ from agentforge.new_path import NewName
```

---

## Coordinated release train

<!-- Per ADR-0015, every framework release bumps every in-scope
     workspace package to the same minor version. List which
     packages went out and what version they're on after this
     release. -->

The release train cut on `<YYYY-MM-DD>` bumps every in-scope
package to `vX.Y.Z`:

| Package | Version | Surface change |
|---|---|---|
| `agentforge-core` | `X.Y.Z` | <one-line summary or "no change"> |
| `agentforge` | `X.Y.Z` | <…> |
| `agentforge-bedrock` | `X.Y.Z` | <…> |
| `agentforge-memory-sqlite` | `X.Y.Z` | <…> |
| `agentforge-memory-postgres` | `X.Y.Z` | <…> |
| `agentforge-memory-neo4j` | `X.Y.Z` | <…> |
| `agentforge-memory-surrealdb` | `X.Y.Z` | <…> |
| `agentforge-eval-geval` | `X.Y.Z` | <…> |
| `agentforge-otel` | `X.Y.Z` | <…> |
| `agentforge-testing` | `X.Y.Z` | <…> |
| `agentforge-guard-llmguard` | `X.Y.Z` | <…> |
| `agentforge-guard-presidio` | `X.Y.Z` | <…> |
| `agentforge-guard-nemo` | `X.Y.Z` | <…> |
| `agentforge-guard-llamaguard` | `X.Y.Z` | <…> |
| `agentforge-mcp` | `X.Y.Z` | <…> |
| `agentforge-chat` | `X.Y.Z` | <…> |
| `agentforge-chat-http` | `X.Y.Z` | <…> |
| `agentforge-a2a` | `X.Y.Z` | <…> |

<!-- Add or remove rows as packages join or leave the train. -->

---

## Cross-language status

<!-- Per ADR-0002, Python ships first during 0.x; TypeScript
     catches up to parity by 0.4. State explicitly which language
     this release covers and where the other stands. -->

- **Python:** released as `vX.Y.Z` on PyPI.
- **TypeScript:** <`pending` | `vN.M.K` | "not yet started">.

---

## Install / upgrade

```bash
# New install
pip install "agentforge[bedrock]==X.Y.Z"

# Upgrade
pip install --upgrade "agentforge==X.Y.Z"
```

For a project scaffolded with an earlier `agentforge new`, run:

```bash
agentforge upgrade --to X.Y.Z
```

(Three-way merge per feat-011; review the diff before accepting.)

---

## Shipped features

<!-- Group by the matching spec at `docs/features/feat-NNN-*.md`.
     For multi-version features (e.g. feat-020 v0.2 scope), list
     which slice landed in this release. -->

| Spec | Surface delivered in this release |
|---|---|
| [feat-NNN](../features/feat-NNN-slug.md) | <bullet rollup> |

---

## Acknowledgements

<!-- Thank contributors. The first release should mention every
     person who's authored or reviewed; subsequent releases just
     since-last-tag. -->

Thanks to <names / handles>. Generated with [Claude
Code](https://claude.com/claude-code) (Anthropic) as the primary
AI co-author across feat-001…feat-020 per the
`Co-Authored-By:` commit trailers.

---

## Full changelog

- [`CHANGELOG.md`](../CHANGELOG.md) — every package's curated
  notes for this release.
- `git log v<X.(Y-1).Z>..vX.Y.Z --oneline` — every commit.
- Compare view: `https://github.com/Scaffoldic/agentforge-py/compare/vX.(Y-1).Z...vX.Y.Z`.
