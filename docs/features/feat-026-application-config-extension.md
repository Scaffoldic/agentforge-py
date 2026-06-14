# feat-026: Application config extension — typed `app:` sections + pluggable sources

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-026 |
| **Title** | Application config extension — reserved `app:` namespace, registered typed sections, pluggable sources |
| **Status** | accepted (design approved; Phase 1 ships via enh-002 in 0.5.0, Phase 2 in this feat) |
| **Owner** | kjoshi |
| **Created** | 2026-06-13 |
| **Target version** | 0.5 (Phase 1) → 0.6 (Phase 2) |
| **Languages** | both |
| **Module package(s)** | `agentforge-core`, `agentforge` |
| **Depends on** | feat-012 (configuration system) |
| **Decision** | [ADR-0022](../adr/0022-app-passthrough-for-application-config.md) |
| **Reported via** | issue #86 (`agentforge-graph`) |

---

## 1. Why this feature

An agent built **on** AgentForge has no sanctioned place for its own
config in `agentforge.yaml`: the root model is strict
(`extra="forbid"`), so any unknown top-level key is rejected. The
workaround — a separate hand-loaded file — forfeits the framework's
`${ENV}` interpolation, env-overlay layering, `--override`, and
`config show --resolved`. Agents end up re-implementing config
machinery the framework already owns (issue #86).

This feature gives application config a first-class, **typed,
validated** home that reuses every part of the feat-012 machinery —
the same way the framework already treats **module** config.

## 2. Why it must ship as framework

feat-012's own thesis applies verbatim: *"Every module reads config…
validation must be uniform; per-module schemas compose."* The
framework already validates `modules.*.config` against each module's
`config_schema` via the resolver (`agentforge_core/config/
module_schemas.py`). Application config validated **differently** —
or not at all — would be an inconsistency in the framework's own
design. A consumer cannot grant their own config interpolation,
layering, `--resolved`, and uniform validation without re-implementing
the loader. Therefore: framework work.

## 3. How derived agents benefit

- One file (`agentforge.yaml`) holds framework **and** app config.
- App config gets `${ENV}` interpolation, `agentforge.<env>.yaml`
  overlays, `--override app.x.y=z`, and `config show --resolved` for
  free (the loader already interpolates/merges the whole tree before
  validation — see feat-012 §4.3).
- `agentforge config validate` catches **app-config** typos too, not
  just framework-key typos — fail-fast parity with modules.
- Typed access: `config.app_as(MyConfig, "graph")` instead of
  hand-walking raw dicts.

## 4. Feature specifications

### 4.1 User-facing experience

```yaml
# agentforge.yaml
agent: { name: my-agent, model: "anthropic:claude-haiku-4-5" }
app:                              # the reserved application namespace
  graph:
    store: { path: ${CKG_PATH:.ckg} }    # interpolation applies
    max_hops: 4
```

```python
# the derived agent declares its section schema (strict, so its own
# keys are typo-checked) and reads it typed:
from agentforge_core.config import load_config

class GraphConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    store: StoreConfig
    max_hops: int = 3

cfg = load_config()
graph = cfg.app_as(GraphConfig, "graph")     # validated GraphConfig
```

```
$ agentforge config validate
# with a registered section schema (Phase 2), a typo under app.graph
# fails here, e.g.:  app.graph.max_hopz: Extra inputs are not permitted
```

### 4.2 Public API / contract

```python
# agentforge_core/config/schema.py — AgentForgeConfig (additive field + method)
class AgentForgeConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")   # unchanged
    app: dict[str, Any] = Field(default_factory=dict)        # NEW — reserved namespace

    def app_as(self, model: type[T], key: str | None = None) -> T:
        """Validate and return an app-config subtree.

        `key=None` validates the whole `app:` block; otherwise the
        `app[key]` subtree. The caller's model owns its own strictness.
        """
        raw = self.app if key is None else self.app.get(key, {})
        return model.model_validate(raw)
```

```python
# Phase 2 — registration mirrors module config_schema discovery (ADR-0004).
# A derived agent / plugin declares an entry point per app-config section:
#
#   [project.entry-points."agentforge.config_sections"]
#   graph = "agentforge_graph.config:GraphConfig"
#
# The framework discovers these and validates the matching app.<section>.
def validate_app_config(cfg: AgentForgeConfig, *, strict: bool = True) -> None:
    """Validate each registered `app.<section>` against its schema.

    Mirrors `validate_module_configs`: unknown/unregistered sections are
    allowed (free-form, like an undocumented `[tool.x]`); registered
    sections are validated strictly. Wired into `agentforge config validate`.
    """
    for section, model in _discover_app_sections():
        if section in cfg.app:
            _validate_section(section, model, cfg.app[section], strict=strict)
```

Adding the `app` field and `app_as` method is **additive** →
minor bump (ADR-0007). The `extra="forbid"` model config is unchanged;
only `app:` is added as a recognized key, so every other unknown
top-level key still fails fast.

### 4.3 Internal mechanics

- **Free machinery (no new code):** `loader.py` already runs
  `_walk` (interpolation) and `_deep_merge` (overlay + `--override`)
  over the raw mapping *before* `model_validate`, and
  `config show --resolved` already does `cfg.model_dump()`. So
  interpolation, layering, overrides, and the resolved view cover
  `app:` the moment the field exists.
- **Section validation (Phase 2)** reuses the resolver +
  `config_schema` pattern from `module_schemas.py`. A new entry-point
  group `agentforge.config_sections` maps `app.<section>` → Pydantic
  model. `strict=False` mode (as in `validate_module_configs`) lets
  `config validate` run against sections whose package isn't installed.

### 4.4 Sections vs sources (the two axes)

This feature deliberately separates two concerns that are often
conflated:

- **Sections** (this feat, Phases 1–2): *typed, namespaced* config
  under `app:`. Pattern: Spring Boot `@ConfigurationProperties(prefix)`,
  Python `pyproject.toml` `[tool.<name>]`. Each owner validates its
  own subtree.
- **Sources** (Phase 3, deferred): *where config comes from*. Today the
  loader has a fixed source list (base file → `agentforge.<env>.yaml`
  overlay → env interpolation → `--override`). Phase 3 generalizes this
  into an ordered, pluggable source list so an app can register an
  **additional file** (e.g. `graph.yaml`) that still flows through
  interpolation, layering, `--resolved`, and validation. Pattern:
  Spring `spring.config.import`, Viper multi-source, kustomize layers.
  Built only on demand — it directly answers the "tomorrow someone
  wants their own config file" need without forfeiting the machinery.

### 4.5 Phasing

| Phase | Scope | Ships in | Spec |
|---|---|---|---|
| **1** | `app:` field + `app_as()` accessor + docs | **0.5.0** | [enh-002](../enhancements/enh-002-app-config-passthrough.md) |
| **2** | Registered typed sections (entry points) + `config validate` coverage | 0.6 | this feat |
| **3** | Pluggable config **sources** (extra files) | on demand | this feat §4.4 |

Phase 1 is a forward-compatible slice: `app.<section>` becomes a
registered section in Phase 2 with **no breaking change** — the raw
dict simply gains framework validation.

## 5. Plug-and-play & upgrade story

`app:` defaults to `{}`; existing configs are unaffected (additive).
A scaffolded agent can adopt app config incrementally: drop keys under
`app:` (free-form) → add an `app_as` model for typed access → register
the section (Phase 2) for `config validate` coverage. Each step is
optional and non-breaking.

## 6. Cross-language parity

The TypeScript runtime mirrors the same shape: a reserved `app`
property on the root config object, a typed `appAs(schema, key)`
accessor (Zod), and (Phase 2) section registration via npm
`exports`-based discovery, consistent with ADR-0002 / ADR-0004.

## 7. Test strategy

- **Phase 1 unit:** `app:` block validates; an unknown *non-`app`*
  top-level key still fails (typo protection intact); `${ENV}`
  interpolation + env-overlay + `--override` resolve values nested
  under `app:`; `config show --resolved` includes the resolved `app:`;
  `app_as` returns the validated model and raises on a bad subtree.
- **Phase 2 unit:** a registered section schema validates `app.<section>`
  during `config validate`; a typo under a registered section fails;
  an unregistered section is left untouched; `strict=False` tolerates a
  not-yet-installed section package.
- **Doc test:** the `agentforge-graph` repro from #86 validates.

## 8. Risks & open questions

| Risk / question | Disposition |
|---|---|
| Apps scatter unrelated keys under `app:` | Document the convention: namespace by concern (`app.graph`, `app.telemetry`); one model per section |
| Users expect the framework to validate `app:` even in Phase 1 | Phase 1 docs state the subtree is app-owned until a section schema is registered (Phase 2) |
| Section registration couples `config validate` to app packages being importable | Mirror `validate_module_configs` `strict=False` to degrade gracefully |
| Open: should Phase 2 allow registered **top-level** prefixes (not just under `app:`)? | Default **no** — keep the single `app:` boundary (pyproject `[tool.*]` model). Revisit only if a strong case appears |

## 9. Out of scope

- Loosening `extra="forbid"` on framework keys (rejected in ADR-0022).
- Turing-complete config / templating (ADR-0013 stands).
- Phase 3 pluggable sources beyond the design sketch in §4.4 (built on
  demand).

## 10. References

- Decision: [ADR-0022](../adr/0022-app-passthrough-for-application-config.md)
- Phase 1 spec: [enh-002](../enhancements/enh-002-app-config-passthrough.md)
- Builds on: [feat-012](./feat-012-configuration-system.md) (config system)
- Reported via: issue #86 (`agentforge-graph`)
- Prior art: Spring Boot `@ConfigurationProperties`; Python `pyproject.toml`
  `[tool.*]` (PEP 518); Viper (Go) multi-source; Kubernetes CRDs + annotations
- Related ADRs: [ADR-0013](../adr/0013-configuration-is-data-not-code.md),
  [ADR-0007](../adr/0007-abc-protocol-as-stable-surface.md),
  [ADR-0004](../adr/0004-module-discovery-via-entry-points.md)

## Implementation status

**Phase 1 — shipped (0.5.0).** The reserved `app:` namespace
(`dict[str, Any]`, default `{}`) and the typed accessor
`AgentForgeConfig.app_as(model, key=None)` landed in
`agentforge_core/config/schema.py` per enh-002. `app:` rides the
existing loader passes, so values get `${ENV}` interpolation, env-file
layering, dotted-path overrides, and `config show --resolved` with no
extra wiring; framework keys stay strict (`extra="forbid"`). Covered by
`tests/unit/test_config_app_passthrough.py` (11 tests: field default,
acceptance, intact typo-protection on non-`app` keys, `app_as` keyed /
whole / missing-key / delegated-strictness, interpolation + env-file
layering inside `app:`, and resolved-dump inclusion). ADR-0022 accepted.

**Phase 2 — not started.** Registered typed sections via the
`agentforge.config_sections` entry-point group, validated in
`agentforge config validate` by reusing the `module_schemas.py` engine.
Targeted at 0.6.

**Phase 3 — not started.** Pluggable config *sources* (separate files,
`spring.config.import`-style). On demand.
