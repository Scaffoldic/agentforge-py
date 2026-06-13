# enh-002: Sanctioned `app:` extension point for application config

> Improves a *shipped* feature (feat-012, configuration system). Filed as
> issue #86 by `agentforge-graph` while building on agentforge-py 0.2.4.
> Not a defect — strict validation works as designed; this adds a missing
> extension point so agents can reuse the framework's config machinery.
> Design decision recorded in [ADR-0022](../adr/0022-app-passthrough-for-application-config.md).

---

## Metadata

| Field | Value |
|---|---|
| **ID** | enh-002 |
| **Title** | Reserved `app:` block for application config in `agentforge.yaml` |
| **Status** | `proposed` |
| **Owner** | kjoshi |
| **Created** | 2026-06-13 |
| **Target version** | 0.5.0 |
| **Languages** | `python` (TypeScript to follow under contract parity) |
| **Improves** | feat-012 (configuration system) |

---

## 1. Summary

Add a single reserved top-level key, `app:`, to `agentforge.yaml` that the
framework accepts but does not interpret. A consuming agent puts its own
config under `app:` and validates that subtree with its own Pydantic
model. Strict validation (`extra="forbid"`) stays in force for every other
top-level key, so framework-key typos are still caught.

## 2. Motivation

`AgentForgeConfig` is strict, so an agent built on AgentForge cannot put
its own config in `agentforge.yaml`:

```
$ agentforge config validate
agentforge.yaml validation failed:
  graph: Extra inputs are not permitted
```

The workaround (a separate `ckg.yaml` loaded by the agent) works but
misses the framework's `${ENV}` interpolation, layered env-file support,
and `config show --resolved`. Agents end up re-implementing config
machinery the framework already has. See issue #86.

## 2.5 Framework-level vs derived-agent-level

**Framework.** The config loader, the `${ENV}` interpolation pass, env-file
layering, and `config show --resolved` are all framework-owned. A consumer
cannot grant *their own* config those capabilities without re-implementing
the loader — exactly the workaround #86 describes.

- **Derived-agent test:** the workaround (separate file + hand-rolled
  interpolation/layering) re-implements framework-owned config machinery →
  fails the test → framework work.
- **How it helps derived agents:** an agent declares its config under
  `app:` in the one file it already ships, and gets interpolation,
  layering, and `--resolved` for free — while the framework keeps strict
  typo-checking on its own keys.

## 3. Before / after

| Aspect | Before | After |
|---|---|---|
| App config in `agentforge.yaml` | rejected (`extra="forbid"`) | allowed under `app:` |
| `${ENV}` interpolation for app config | only via hand-rolled loader | free, under `app:` |
| `config show --resolved` | framework keys only | includes resolved `app:` |
| Framework-key typo protection | strict | **still strict** (unchanged) |

```yaml
# after
agent: { name: my-agent, model: "anthropic:claude-haiku-4-5" }
app:
  graph:
    store: { path: ${CKG_PATH:.ckg} }
```

```python
# consuming agent validates its own subtree
class GraphConfig(BaseModel):
    store: StoreConfig

cfg = load_config("agentforge.yaml")        # framework loader
graph_cfg = GraphConfig.model_validate(cfg.app["graph"])
```

## 4. Backward compatibility

Additive and safe. `app` defaults to `{}`; existing configs that never set
it are unaffected. Adding a field with a safe default is a minor bump
under ADR-0007. No framework behavior changes; only a previously-rejected
key becomes accepted.

## 5. Implementation sketch

- Add `app: dict[str, Any] = Field(default_factory=dict)` to
  `AgentForgeConfig` (`agentforge_core/config/schema.py`). Keep
  `model_config = ConfigDict(strict=True, extra="forbid")` — only `app:`
  is added as a recognized field; everything else stays strict.
- Confirm the interpolation + layering passes already operate on the raw
  mapping (so values inside `app:` get `${ENV}` resolution and env-file
  layering with no extra wiring). Add coverage if any pass special-cases
  known keys.
- Ensure `config show --resolved` emits the resolved `app:` subtree.
- The framework performs **no** schema validation inside `app:` — that is
  the consuming agent's responsibility (documented explicitly).

## 6. Test plan

- Unit: a config with an `app:` block validates; an unknown *non-`app`*
  top-level key (`graph:` at the root) still fails — typo protection
  intact.
- Unit: `${ENV}` interpolation and env-file layering resolve values nested
  under `app:`.
- Unit: `config show --resolved` includes the resolved `app:` subtree.
- Doc test / example: the `agentforge-graph` repro from #86 now validates.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Apps treat `app:` as a dumping ground / scatter unrelated keys | Document the convention: one namespaced subtree, validated by the app's own model |
| Users expect the framework to validate inside `app:` | Document clearly that the subtree is app-owned; `config validate` only checks framework keys |
| Future demand for fully separate app files | `app:` does not preclude an "additional config files" mechanism later (ADR-0022 option 3) — it can layer on top |

## 8. References

- Reported in: issue #86 (`agentforge-graph`)
- Decision: [ADR-0022](../adr/0022-app-passthrough-for-application-config.md)
- Improves: feat-012 (configuration system)
- Related: ADR-0013 (configuration is data, not code)
