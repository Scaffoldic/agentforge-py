# ADR-0015: Coordinated release train across all packages

## Metadata

| Field | Value |
|---|---|
| **Number** | 0015 |
| **Title** | Coordinated release train across all packages |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | release-engineering, packaging |

---

## 1. Context and problem statement

The three-tier package model (ADR-0003) splits the framework into many
pip / npm packages. LlamaIndex's experience with ~300 independent
packages is cautionary: any minor `core` bump can break long-tail
integrations, version-matrix maintenance becomes a full-time job, and
users hit dependency-resolution hell.

How do we coordinate releases so the modular structure delivers the
benefits of separation without the drift cost?

## 2. Decision drivers

- Modules pin against `agentforge-core`; mismatched versions break runtime
- Conformance suites are shared; old modules must keep passing
- Users `pip install` multiple modules and expect them to compose
- Maintainer cost of N independent release cycles is high

## 3. Considered options

1. **Independent versioning, free release cadence** — LlamaIndex shape
2. **Single mono-version (every package gets the same number)** —
   AutoGen v0.4 shape
3. **Coordinated train** — the framework cuts a release that bumps every
   in-scope package to the same minor; modules can patch independently
   between trains
4. **Calver mono-version** — date-based; everything moves together

## 4. Decision outcome

**Chosen: Option 3 — Coordinated release train.**

A framework release (e.g. v0.5.0) cuts every in-scope package to the
same minor version simultaneously. Between releases, individual modules
may publish patch versions (bug fixes only). Every module's `pyproject.toml`
pins `agentforge-core ~=0.5` (compatible with 0.5.x; not 0.6.x). The
release train runs every 2 weeks during 0.x; monthly during 1.x.

This shape mirrors monorepo workspaces (uv workspaces, pnpm workspaces)
and matches how successful multi-package frameworks (FastAPI ecosystem,
Hono ecosystem) actually behave in practice.

### Positive consequences

- "Did you `pip install` the matching versions?" stops being a question
- Conformance suites stay consistent across packages
- Users have one release-notes document to read
- Marketing has one version number to talk about

### Negative consequences (trade-offs)

- Patch releases are constrained (bug fixes only between trains)
- A bug in one module can't be fixed standalone if it would require a
  contract change — but contract changes are rare by design
- Some communities expect per-package independence and may push back

## 5. Pros and cons of the options

### Option 1: Independent versioning

- + Module authors fully autonomous
- − LlamaIndex matrix-hell precedent

### Option 2: Mono-version

- + Maximum simplicity
- − No way to ship a hotfix to one module without bumping all

### Option 3: Coordinated train (chosen)

- + Predictable; users have one number to track
- + Hotfixes still possible via patch versions
- − Train cadence sets a max delay for non-critical changes

### Option 4: Calver mono-version

- + Even simpler
- − Loses semver semantics; module authors can't communicate "breaking"

## 6. References

- ADR-0003 (three-tier package model)
- [`docs/design/architecture.md`](../design/architecture.md) §10
