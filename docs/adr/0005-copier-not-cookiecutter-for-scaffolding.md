# ADR-0005: Copier (not Cookiecutter) for scaffolding and upgrades

## Metadata

| Field | Value |
|---|---|
| **Number** | 0005 |
| **Title** | Copier (not Cookiecutter) for scaffolding and upgrades |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | scaffolding, upgrade, dx |

---

## 1. Context and problem statement

Scaffolding is solved (cookiecutter, yeoman, copier, plop, etc.). The hard
part is **upgrading a generated project six months later** when the
framework has moved on. Cookiecutter is one-shot; it has no answer for
"the template now has new content, can you bring it into my existing
project without losing my customisations?"

a predecessor project's `template-sync` was an attempt; it was incomplete. Most agent
frameworks today don't even try, leaving long-lived agents stuck on old
versions.

How do we pick a scaffolding tool that supports both initial generation
*and* later updates with three-way merge?

## 2. Decision drivers

- The upgrade path must work for the lifetime of an agent (P8: upgrade-safe
  by construction)
- Tool must be mature, actively maintained, and ecosystem-fit
- Must support three-way merge so developer customisations survive
- Template syntax must be approachable (Jinja, Handlebars, etc.)
- Must work in both Python and TS scaffolding contexts

## 3. Considered options

1. **Cookiecutter** — most popular Python scaffolding tool; one-shot only
2. **Cookiecutter + cruft** — bolt update tracking onto cookiecutter
3. **Copier** — purpose-built for "generate + later update with diff merge"
4. **Bespoke tool** — write our own using Jinja + a simple diff engine

## 4. Decision outcome

**Chosen: Option 3 — Copier.**

Copier is purpose-built for the update-after-generation case. It tracks
the link between project and template in `.copier-answers.yml`, supports
three-way merge automatically, handles conditional prompting, and is
mature (used in production by many projects). The fact that `cruft`
exists is itself evidence that "Cookiecutter + update" is a real demand;
Copier provides it natively rather than as a bolt-on.

For TypeScript scaffolding, a **native TS port** of the same template
format is built (see ADR-0021). The TS port consumes the same
`agentforge-templates` sources Copier consumes, so there is one template
source of truth across both languages. TS users never need Python
installed.

### Positive consequences

- Native three-way merge — no separate tool to bolt on
- Linked template/project state via `.copier-answers.yml`
- Conditional prompts (Jinja in question text) — useful for per-template
  variations
- Active maintenance and a mature user base

### Negative consequences (trade-offs)

- Two engines to maintain (Python: Copier; TypeScript: native port — see
  ADR-0021). Mitigated by sharing a single template source of truth and
  a shared test fixture suite both engines must pass.
- Slightly steeper learning curve than Cookiecutter for template authors
  (worth it for the upgrade benefit)

## 5. Pros and cons of the options

### Option 1: Cookiecutter

- + Most familiar; huge community
- + Simple Jinja templates
- − One-shot only — no update mechanism
- − Defeats the entire upgrade-safe-by-construction goal

### Option 2: Cookiecutter + cruft

- + Familiar surface
- + Adds update tracking
- − Cruft is the bolt-on; Copier is the native version of the same idea
- − Two tools to maintain instead of one

### Option 3: Copier (chosen)

- + Update is first-class
- + Mature and well-maintained
- + Conditional prompting is more flexible than cookiecutter
- − TS gets a native port (ADR-0021) so its users have zero Python footprint

### Option 4: Bespoke

- + Full control
- − Months of work to reach Copier's feature set
- − Maintenance burden for a non-differentiating component

## 6. References

- ADR-0006 (marker-header file ownership)
- ADR-0017 (AGENTS.md as canonical AI rules)
- ADR-0021 (native TypeScript scaffolding engine — companion)
- [`docs/design/scaffolding-and-upgrade.md`](../design/scaffolding-and-upgrade.md)
- [Copier documentation](https://copier.readthedocs.io/)
