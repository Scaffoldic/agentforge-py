# ADR-0021: Native TypeScript scaffolding engine

## Metadata

| Field | Value |
|---|---|
| **Number** | 0021 |
| **Title** | Native TypeScript scaffolding engine (companion to ADR-0005) |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | scaffolding, upgrade, typescript |

---

## 1. Context and problem statement

ADR-0005 chose Copier (Python) as the scaffolding/upgrade engine for
the framework. Because the Python and TypeScript implementations are
**separate git repos** (per the locked structure decision), TS users
should not have to install Python just to run `agentforge new` or
`agentforge upgrade`.

How do we deliver the same scaffolding + three-way-merge upgrade
experience to TypeScript users without forcing a Python dependency?

## 2. Decision drivers

- TS-only teams should have zero Python footprint
- Template format must be compatible with the Python engine so a
  single source of truth (`agentforge-templates`) renders cleanly to
  both languages
- Three-way merge on update is non-negotiable (P8 — upgrade-safe by
  construction)
- Marker-header file ownership (ADR-0006) must work identically
- Maintenance cost of two engines must be acceptable

## 3. Considered options

1. **Wrap Copier from the TS CLI** — TS CLI shells out to Copier,
   requires Python at scaffold/upgrade time
2. **Native TypeScript port** — implement Copier-equivalent semantics
   in TS, no Python dependency
3. **Vendor a Python runtime** in the TS package
4. **Use an existing TS scaffolder** (e.g. degit, Plop) and bolt
   three-way merge on top

## 4. Decision outcome

**Chosen: Option 2 — Native TypeScript port.**

The TS implementation is a clean-room port that consumes the same
template format as Copier (Jinja2-style placeholders, `copier.yml`
config, marker headers per ADR-0006) and implements three-way merge
with a TS diff library (e.g. `diff3`, `node-diff3`). Templates remain
authored in `agentforge-templates`; both engines render the same
sources.

This honours the "separate repos, separate tooling" choice that
shapes the rest of the framework: each language ecosystem stays
self-contained. TS developers don't need Python; Python developers
don't need Node.

### Positive consequences

- Zero cross-language tooling dependency
- TS scaffolding is a first-class npm package, not a wrapper
- Each engine evolves independently within its language's idioms
- Single template source of truth keeps content aligned

### Negative consequences (trade-offs)

- Two engines to maintain (mitigated: template format is small, both
  reach for the same JinjaJS / diff3 libraries)
- Behavioural drift risk between engines — caught by a shared test
  fixture suite that both engines must pass identically
- Initial engineering cost higher than wrapping Copier (~2-3 weeks of
  dedicated work)

## 5. Pros and cons of the options

### Option 1: Wrap Copier

- + Fastest path to functional parity
- − Forces Python on TS users; awkward for pnpm-only teams
- − Subprocess management across platforms is fiddly

### Option 2: Native TypeScript port (chosen)

- + Idiomatic for the TS ecosystem
- + No cross-language deps
- + Long-term path; aligned with separate-repo structure
- − Engineering cost upfront; behavioural drift risk

### Option 3: Vendored Python runtime

- + Hides the dependency
- − Massive package size; security concerns; fragile

### Option 4: Existing TS scaffolder + bolted merge

- + Reuses ecosystem tooling
- − No mature TS scaffolder offers three-way merge today
- − "Bolting on" merge produces the cruft pattern

## 6. References

- ADR-0005 (Python: Copier) — companion decision
- ADR-0006 (marker-header file ownership) — same mechanism in TS
- [`docs/features/feat-011-scaffolding-and-upgrade.md`](../features/feat-011-scaffolding-and-upgrade.md) §4.9
- [`docs/design/scaffolding-and-upgrade.md`](../design/scaffolding-and-upgrade.md)
- Copier docs (template format reference): https://copier.readthedocs.io/
- node-diff3: https://github.com/bhousel/node-diff3
