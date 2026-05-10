# ADR-0004: Module discovery via Python entry points / npm exports

## Metadata

| Field | Value |
|---|---|
| **Number** | 0004 |
| **Title** | Module discovery via Python entry points / npm exports |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, modules, plug-and-play |

---

## 1. Context and problem statement

When a developer installs a module package (e.g. `agentforge-memory-postgres`),
something must connect that installation to the framework's runtime so the
module is reachable by name from `agentforge.yaml`. The mechanism must be
static (inspectable without running user code), safe (no arbitrary path
loading), and idiomatic in both Python and TypeScript.

How do modules register themselves with the framework so a `pip install`
plus a config edit is sufficient, with no manual wiring?

## 2. Decision drivers

- Static inspectability — `agentforge list modules` must enumerate
  registrations without executing user code
- Standard ecosystem mechanism — don't invent
- Same shape in Python and TypeScript
- Fail-at-startup (P11) — missing modules surface immediately, not at hour 2
- No dynamic-import-from-arbitrary-path footguns (P5)

## 3. Considered options

1. **Python entry points** + **npm `package.json` exports** — standard,
   declarative, statically discoverable in both ecosystems
2. **Auto-import by package-name pattern** (e.g. import every `agentforge_*`
   on the path) — convention only, no explicit registration
3. **Manual registration in user code** — every agent imports + calls
   `register(...)` for each module
4. **YAML-driven dynamic import** — `module: "myapp.providers:MyClient"`
   loads the path at startup

## 4. Decision outcome

**Chosen: Option 1 — entry points (Py) + `package.json` exports (TS).**

This is the standard mechanism in both ecosystems. A module's
`pyproject.toml` declares:

```toml
[project.entry-points."agentforge.memory"]
postgres = "agentforge_memory_postgres:PostgresMemoryStore"
```

And in TS, `package.json` carries an `agentforge` field with the same
information. The framework's `Resolver` reads `importlib.metadata`
(Python) or scans installed packages' `agentforge` field (TS) at startup,
builds a `(category, name) → class` map, and uses it to resolve YAML
references like `modules.memory.driver: postgres`.

A decorator-based fallback (`@register("memory", "my-store")`) is also
provided for in-repo agent modules that don't ship as separate packages.

### Positive consequences

- Standard tooling — `pip show -f`, `npm ls` reveal registrations naturally
- Static discovery — no need to import modules to know they exist
- Multi-language uniformity at the conceptual level
- Safe — entry points cannot execute arbitrary file paths

### Negative consequences (trade-offs)

- Slightly slower startup on installations with many modules (mitigated
  by caching the entry-point map)
- TS doesn't have a native exact equivalent; we adopt a `package.json`
  field that requires our own scanner

## 5. Pros and cons of the options

### Option 1: Entry points / package.json exports (chosen)

- + Standard, statically inspectable
- + Safe; no arbitrary path loading
- + Same conceptual model in both languages
- − Adds a small startup scan cost; cached after first run

### Option 2: Auto-import by name pattern

- + Zero configuration
- − Brittle; package renames break things silently
- − Not discoverable; can't list registrations

### Option 3: Manual registration in user code

- + Explicit
- − Re-imposes the boilerplate the framework is meant to eliminate

### Option 4: YAML-driven dynamic import

- + Flexible
- − Violates P5 (config is data, not code); turns YAML into Python paths
- − Major attack surface

## 6. References

- ADR-0003 (three-tier package model)
- ADR-0013 (configuration is data, not code)
- [`docs/design/module-system.md`](../design/module-system.md)
- [Python packaging: entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
- [`importlib.metadata`](https://docs.python.org/3/library/importlib.metadata.html)
