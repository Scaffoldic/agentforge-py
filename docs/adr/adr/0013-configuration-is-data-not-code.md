# ADR-0013: Configuration is declarative data (not Turing-complete)

## Metadata

| Field | Value |
|---|---|
| **Number** | 0013 |
| **Title** | Configuration is declarative data (not Turing-complete) |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, config |

---

## 1. Context and problem statement

Configuration files often slide into being de-facto code: dynamic
imports of arbitrary paths, function names as strings, Jinja templating
of runtime logic, conditional branches encoded as YAML structures.
Once that happens, the security boundary blurs, the schema becomes
unverifiable, and tooling like "show me the resolved config" becomes
impossible.

How do we keep `agentforge.yaml` clear, auditable, and statically
analysable while still expressive enough for real agents?

## 2. Decision drivers

- Static analysis must be possible (`agentforge config validate`,
  `agentforge config show`)
- Security: config files are often committed to repos; arbitrary code
  in YAML is an attack vector
- Modules must be selected by name, not by path
- Env-var interpolation is necessary (secrets injection); other
  templating is not
- Schema must be version-able

## 3. Considered options

1. **Turing-complete YAML (Jinja inside YAML, dynamic-import paths)** —
   maximum power
2. **Pure declarative YAML + env-var interpolation** — restricted, but
   covers real cases
3. **TOML / INI** — even more restrictive
4. **Python code as config** (Django settings.py model) — full power,
   no schema

## 4. Decision outcome

**Chosen: Option 2 — Pure declarative YAML + env-var interpolation.**

`agentforge.yaml` is data: a tree of key/value pairs validated against
a Pydantic / Zod schema composed from per-module schemas. The only
"templating" is env-var interpolation: `${VAR}`, `${VAR:default}`,
`${VAR:?error message}`, `$$` for literal `$`. No Jinja, no dynamic
imports, no inline Python. Modules are selected by name (resolver
looks up the entry point per ADR-0004), never by path. Behavioural
overrides go in code or are exposed as additional config knobs in the
relevant module's schema.

### Positive consequences

- `agentforge config validate` and `agentforge config show` are
  meaningful operations
- Config files are safe to read at audit time
- Schema autocomplete in editors via JSON Schema export
- No surprise behaviour from "logic in YAML"

### Negative consequences (trade-offs)

- Some users will want logic in config; we say no and point to code
- A small ergonomic loss vs Jinja-in-YAML for advanced users
- TOML supporters will be disappointed (deferred indefinitely)

## 5. Pros and cons of the options

### Option 1: Turing-complete YAML

- + Maximum flexibility
- − Security and auditability nightmare; defeats P5

### Option 2: Pure declarative + env-vars (chosen)

- + Safe, auditable, schema-able
- + Editor autocomplete via JSON Schema
- − Some ergonomic loss for power users

### Option 3: TOML / INI

- + Even safer
- − Verbose; doesn't model nested structures cleanly

### Option 4: Python config

- + Full power; familiar to Django users
- − No schema; no static analysis; can't be lint-checked

## 6. References

- [`docs/design/design-principles.md`](../design/design-principles.md) — P5
- ADR-0004 (modules selected by entry-point name, not path)
- [`docs/features/feat-012-configuration-system.md`](../features/feat-012-configuration-system.md)
