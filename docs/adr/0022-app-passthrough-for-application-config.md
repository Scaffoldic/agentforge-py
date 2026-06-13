# ADR-0022: Reserved `app:` block for application config in `agentforge.yaml`

## Metadata

| Field | Value |
|---|---|
| **Number** | 0022 |
| **Title** | Reserved `app:` block for application config in `agentforge.yaml` |
| **Status** | Proposed |
| **Date** | 2026-06-13 |
| **Deciders** | kjoshi |
| **Tags** | architecture, config |

---

## 1. Context and problem statement

The root config model `AgentForgeConfig` is strict
(`ConfigDict(strict=True, extra="forbid")`). Any top-level key the
framework doesn't define is rejected:

```yaml
# agentforge.yaml
agent: { name: my-agent, model: "anthropic:claude-haiku-4-5" }
graph:                       # the agent's own engine config
  store: { path: .ckg }
```

```
$ agentforge config validate
agentforge.yaml validation failed:
  graph: Extra inputs are not permitted
```

Strict validation is deliberate and load-bearing: it catches typos in
framework keys (`agnet:`, `modlues:`) at config-load time rather than
silently ignoring them. We do **not** want to give that up.

But the strictness has a side effect: an agent built *on* AgentForge
(reported by `agentforge-graph`, issue #86) has **no sanctioned place
for its own config** inside `agentforge.yaml`. The workaround — a
separate `ckg.yaml` loaded by the agent package — works, but that file
misses the framework's `${ENV}` interpolation, layered env-file support,
and `config show --resolved`. The framework's (good) config machinery
is not reusable by the very agents the framework exists to serve.

How do we give application config a sanctioned home **without** weakening
typo protection for framework keys?

## 2. Decision drivers

- **Typo protection must stay.** `extra="forbid"` on framework keys is a
  stated value (catches `agnet:`); relaxing it globally is a regression.
- **The framework exists to serve agents built on it.** A "plug-and-play
  framework for building production agents" should let those agents reuse
  its config machinery (interpolation, layering, `--resolved`), not force
  them to re-implement it.
- **Config is data, not code (ADR-0013).** Any extension point must stay
  declarative — no dynamic imports, no executable behavior introduced by
  the app's subtree.
- **Contract stability (ADR-0007).** Adding a field with a safe default to
  `AgentForgeConfig` is a minor bump; removing or renaming is major. We
  prefer the smallest additive change.
- **Consistency with the framework's own pattern.** The framework *already*
  validates per-component config sections: `module_schemas.py` walks
  `modules.*`, resolves each driver via the entry-point resolver (ADR-0004),
  reads its `config_schema`, and validates that section. feat-012's thesis is
  *"validation must be uniform; per-module schemas compose."* App config
  validated **differently** from module config would be an inconsistency in
  our own design — so the end state should let app config register a typed,
  validated section the same way modules do.
- **Match the proven industry pattern.** "One shared config file, a reserved
  namespace, many typed sub-sections each owned and validated by its
  component" is the mature, widely-adopted answer: Spring Boot
  `@ConfigurationProperties(prefix)`, Python `pyproject.toml` `[tool.<name>]`
  (PEP 518), Kubernetes CRDs/annotations, Viper multi-source. We adopt it
  rather than invent.

## 3. Considered options

1. **Reserved `app:` passthrough block** — one top-level key the framework
   accepts but does not interpret; the app validates its own subtree.
2. **OpenAPI-style `x-*` extension keys** — allow any top-level key
   prefixed `x-`, ignore them in the framework model.
3. **Additional config files mechanism** — the framework discovers and
   loads a separate app config file and surfaces it through the same
   interpolation/layering/`--resolved` machinery.
4. **Document-only** — keep strict validation, document that app config
   belongs in a separate file and that the split is intentional.
5. **Relax `extra="forbid"` globally** — allow any unknown key.

## 4. Decision outcome

**Chosen: Option 1 — a reserved `app:` block.**

Add a single field to `AgentForgeConfig`:

```python
app: dict[str, Any] = Field(default_factory=dict)
"""Sanctioned passthrough for application config. The framework does
not interpret this subtree — a consuming agent validates `config.app`
with its own Pydantic model. Everything else stays strict."""
```

`extra="forbid"` is unchanged, so every *other* unknown top-level key is
still rejected — `agnet:` still fails fast. Only `app:` is blessed.
Because `${ENV}` interpolation and env-file layering run over the raw
mapping (which now includes `app:`), and `app` is a real field, the app's
config gets interpolation, layering, and `config show --resolved` for
free. The consuming agent is responsible for validating the *shape* of
its own `app:` subtree.

### Phasing — `app:` is the namespace; typed registered sections are the destination

The reserved `app:` block is the **namespace** (the `[tool]` of
`agentforge.yaml`). The decision is delivered in phases so #86 is unblocked
immediately without building speculative machinery:

- **Phase 1 (enh-002, 0.5.0):** the `app:` field + a typed accessor
  `config.app_as(model, key)`. The agent validates its subtree with its own
  (strict, if it likes) model — so typo protection inside `app:` is
  *delegated*, not lost.
- **Phase 2 (feat-026):** registered typed sections. A derived agent/plugin
  declares `app.<section> → PydanticModel` via an entry-point group
  (`agentforge.config_sections`), and the framework validates it during
  `config validate` — reusing the **existing** `module_schemas.py` engine, so
  app config becomes a first-class, framework-validated section exactly like
  `modules.*`. Phase 1 is forward-compatible: `app.<section>` simply gains
  framework validation, with no breaking change.
- **Phase 3 (feat-026 §4.4, on demand):** pluggable config **sources** — let
  an app register an additional file (e.g. `graph.yaml`) that still flows
  through interpolation/layering/`--resolved`/validation. This is the separate
  "sources" axis (Spring `spring.config.import`, Viper), distinct from the
  "sections" (typed namespaces) axis above. Built only when a real need
  appears.

So this ADR blesses both the immediate `app:` block **and** the typed-section
destination it grows into; feat-026 carries the full design.

```yaml
# agentforge.yaml — after
agent: { name: my-agent, model: "anthropic:claude-haiku-4-5" }
app:
  graph:
    store: { path: ${CKG_PATH:.ckg} }   # interpolation now applies
```

### Positive consequences

- One file. App config reuses **all** the framework config machinery.
- Typo protection for framework keys is fully preserved.
- Minimal, additive contract change — a minor version bump per ADR-0007.
- Stays declarative data — no dynamic behavior (consistent with ADR-0013).

### Negative consequences (trade-offs)

- The framework does **not** validate inside `app:` — that is delegated to
  the app. (This is correct: the framework cannot know the app's schema.)
- A single namespace: apps must nest their own structure under `app:`
  rather than scattering top-level keys.
- Slight blur of "framework config file" vs "app config" ownership, which
  the docs must address (the `app:` subtree is owned by the app).

## 5. Pros and cons of the options

### Option 1: Reserved `app:` block (chosen)

- + Smallest additive change; reuses all machinery; typo protection intact
- + Clear, single, documented ownership boundary
- − Framework can't validate the subtree (delegated to the app, by design)

### Option 2: `x-*` extension keys

- + Familiar (OpenAPI); multiple top-level extension keys
- − Multiple escape hatches dilute the "one home for app config" story
- − Pydantic can't express "allow keys matching a prefix" as cleanly as a
  single named field; needs a custom validator + still loosens the model

### Option 3: Additional config files

- + Clean file separation; `agentforge.yaml` stays framework-only; scales
- − Much more machinery (discovery, load order, merge semantics, how it
  surfaces in `--resolved`); larger surface for a modest need
- − Defer-able: can be added later *on top of* `app:` if demand appears

### Option 4: Document-only

- + Zero code; strict contract stays pristine
- − Does not solve the reported need — the separate file still misses
  interpolation/layering/`--resolved`; blesses the unsatisfying workaround

### Option 5: Relax `extra="forbid"` globally

- + Trivial
- − **Regression**: loses framework-key typo protection — the exact thing
  the strictness was introduced to provide. Rejected.

## 6. References

- Reported in: issue #86 (filed by `agentforge-graph`)
- Phase 1 (`app:` field + accessor): [`docs/enhancements/enh-002-app-config-passthrough.md`](../enhancements/enh-002-app-config-passthrough.md)
- Full capability + phasing: [`docs/features/feat-026-application-config-extension.md`](../features/feat-026-application-config-extension.md)
- Improves: [`docs/features/feat-012-configuration-system.md`](../features/feat-012-configuration-system.md)
  (esp. `agentforge_core/config/module_schemas.py` — the existing per-section validation engine)
- Related ADRs: [ADR-0013](./0013-configuration-is-data-not-code.md) (config is data),
  [ADR-0007](./0007-abc-protocol-as-stable-surface.md) (contract stability / minor-bump rule),
  [ADR-0004](./0004-module-discovery-via-entry-points.md) (entry-point discovery — reused for section registration)
- Prior art: Spring Boot `@ConfigurationProperties`; Python `pyproject.toml`
  `[tool.*]` (PEP 518); Viper (Go) multi-source; Kubernetes CRDs + annotations
