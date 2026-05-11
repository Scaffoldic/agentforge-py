# feat-012: Configuration system

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-012 |
| **Title** | Configuration — `agentforge.yaml` schema, env interpolation, validation, dotted overrides |
| **Status** | shipped (Python — runtime + module-schema integration + `agentforge config` CLI) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 |
| **Languages** | both |
| **Module package(s)** | `agentforge-core`, `agentforge` |
| **Depends on** | feat-001 |
| **Blocks** | feat-005, feat-006, feat-009, feat-010 (all consume config) |

---

## 1. Why this feature

A framework's config story makes or breaks adoption. Too rigid: developers
fight it. Too flexible: config becomes code, errors surface at runtime, and
nobody can answer "what is this agent actually doing?" by reading one file.

Pain we have seen: agents that scatter configuration across `config/*.yaml`,
env vars, YAML imports, `.envrc`, and constructor kwargs. By the time someone
debugs production, finding the actual setting takes thirty minutes of
greppage. Or: agents that put behaviour in config (function names as strings,
dynamic imports), then break catastrophically when a typo flips the load
order.

## 2. Why it must ship as framework

- **Every module reads config.** If config format isn't standard, every
  module reinvents loading + validation + interpolation.
- **Validation must be uniform.** Pydantic / Zod schemas per module compose
  into one root model; the framework owns composition.
- **Env-var interpolation needs consistent rules.** `${VAR}`, `${VAR:default}`,
  required vs optional — pin once, reuse everywhere.
- **P5 (configuration is data; behaviour is code) requires a framework that
  enforces the boundary.** Without it, "config" becomes "dynamic-import.yaml"
  and the framework's invariants leak.
- **Without framework ownership:** drift across modules, runtime failures
  instead of startup failures, no `agentforge config validate` is possible.

## 3. How derived agents benefit

- **One file to read, one source of truth.** `agentforge.yaml` shows
  everything: model, strategy, modules, observability, budgets.
- **`agentforge config validate`** catches typos before the agent runs.
- **`agentforge config show`** prints the fully resolved config (env vars
  interpolated, defaults applied) — exactly what the agent will see.
- **Dotted-path overrides for tests / experiments.** `agent.budget.usd=10`
  on the CLI overrides without editing the file.
- **Per-environment files.** `agentforge.yaml` + `agentforge.production.yaml`
  layered; the framework picks the right one by `AGENTFORGE_ENV`.
- **Config schema travels with each module.** When a developer adds a new
  module, IDE autocomplete + JSON-schema-driven YAML completion guide them
  to the right keys.

## 4. Feature specifications

### 4.1 User-facing experience

```yaml
# agentforge.yaml (a complete real-world example)
agent:
  name: "pr-reviewer"
  model: "anthropic:claude-sonnet-4.7"
  strategy: "react"
  system_prompt_file: "./prompts/system.md"
  budget:
    usd: 5.0
    max_tokens: 200000
  max_iterations: 50

modules:
  memory:
    driver: postgres
    config:
      dsn: "${POSTGRES_DSN}"
      project: "${AGENTFORGE_AGENT_NAME:my-agent}"

  evaluators:
    - faithfulness
    - geval:
        rubric: "code-review-correctness"
        cost_cap_usd: 0.20

  observability:
    - name: otel
      config:
        endpoint: "${OTEL_ENDPOINT:http://localhost:4317}"

logging:
  level: "${LOG_LEVEL:INFO}"
  format: "json"
```

```bash
agentforge config validate
agentforge config show
agentforge config show --resolved      # with env vars interpolated
agentforge run "..." --override agent.budget.usd=10
```

### 4.2 Public API / contract

```python
# agentforge_core/config/schema.py — locked root models
class AgentForgeConfig(BaseModel):
    agent: AgentConfig
    modules: ModulesConfig = ModulesConfig()
    logging: LoggingConfig = LoggingConfig()
    providers: dict[str, dict[str, Any]] = {}
    output: OutputConfig = OutputConfig()

class AgentConfig(BaseModel):
    name: str | None = None
    model: str | dict[str, Any]
    strategy: str | dict[str, Any] = "react"
    tools: list[str | dict[str, Any]] = []
    system_prompt: str | None = None
    system_prompt_file: Path | None = None
    budget: BudgetPolicy = BudgetPolicy()
    max_iterations: int = 25
    llm_options: dict[str, Any] = {}

# agentforge_core/config/loader.py
def load_config(
    path: Path | str | None = None,
    *,
    env: str | None = None,           # "production" | "staging" | ...
    overrides: list[str] | None = None,  # ["agent.budget.usd=10", ...]
) -> AgentForgeConfig: ...

# Module-side schema integration (each module ships a Pydantic model)
class PostgresMemoryConfig(BaseModel):
    dsn: str
    project: str = "default"
    pool: PoolConfig = PoolConfig()
```

### 4.3 Internal mechanics

Resolution order (last wins):

1. Defaults from each module's Pydantic schema
2. `agentforge.yaml`
3. `agentforge.<env>.yaml` (if `AGENTFORGE_ENV` set)
4. Env-var interpolation inside YAML values
5. CLI `--override` arguments (dotted path)
6. Constructor kwargs to `Agent(...)`

Env-var syntax:

- `${VAR}` — required; raise at load if missing
- `${VAR:default}` — optional with default
- `${VAR:?error message}` — required with custom error
- `$$` — literal `$`

Validation runs after merge, before any module instantiation. Errors include
the YAML path and the offending value.

### 4.4 Module packaging

Loader + root schema in `agentforge-core`. CLI subcommands in `agentforge`.
Each module ships its own Pydantic schema; the resolver pulls them together.

### 4.5 Configuration

The feature *is* the configuration. Configurable knobs of the loader itself
are limited:

| Env var | Purpose |
|---|---|
| `AGENTFORGE_ENV` | Selects layered config file (`agentforge.<env>.yaml`) |
| `AGENTFORGE_CONFIG` | Override path to root config file |
| `AGENTFORGE_LOG_LEVEL` | Convenience override for `logging.level` |

## 5. Plug-and-play & upgrade story

The schema grows on minor framework bumps; new fields ship with safe
defaults so existing configs remain valid. Removed fields go through a
deprecation cycle (warning for one minor version, removal next major).

`agentforge config migrate` (future) helps move configs across major
bumps.

## 6. Cross-language parity

YAML schema identical between languages. Python uses Pydantic; TS uses Zod.
The two implementations are tested against the same fixture set.

## 7. Test strategy

- **Schema validation:** invalid YAML → clear error with path + reason
- **Env-var interpolation:** every syntax form covered
- **Override precedence:** layered fixture asserts each level wins where
  expected
- **Config schema export:** `agentforge config schema` produces JSON Schema
  for editor autocomplete; snapshot test
- **Cross-language parity:** same fixture YAML loads to equivalent typed
  models in Py and TS

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| YAML hostility (anchors, multi-doc, type coercion bugs) | Use `yaml.safe_load` with explicit types; document the supported subset |
| Should we also support TOML? | Defer; YAML covers the audience; TOML support in v0.x is YAGNI |
| Secrets in config files | We do *not* support inline secrets — env-var interpolation is the path; pre-commit hook detects suspected secret strings |
| Schema-export drift across modules | CI gate: `agentforge config schema` regenerated and compared on every release |
| Per-environment file proliferation | Document the recommended pattern: `agentforge.yaml` (defaults) + `agentforge.production.yaml` (overrides) — no nested includes |

## 9. Out of scope

- Live config reload. Configs are read at agent construction; restart to
  change.
- Templating beyond env-var interpolation. No Jinja, no `{{ }}` in YAML.
  Logic in YAML is a P5 violation.
- Config encryption at rest. Use Vault / SOPS / equivalents around the
  framework.

## 10. References

- [`design-principles.md`](../design/design-principles.md) — P5
- feat-001, feat-010, feat-011, feat-017

---

## Implementation status

**Status: shipped (Python).** Landed across 11 chunks on
`feat/012-configuration-system`. Target version 0.1 — foundational.

| Chunk | Scope |
|---|---|
| 1-2 | Move schema + loader from `agentforge.config` to `agentforge-core.config` so the resolver layer can compose module schemas without a runtime-package dep; widened root schema (`BudgetConfig`, `ModulesConfig`, `ProvidersConfig`, `OutputConfig`, evaluator / observability sub-shapes). |
| 3-6 | `system_prompt_file: Path` support; layered env files (`AGENTFORGE_ENV` → overlay); dotted-path overrides (`parse_overrides`); `AGENTFORGE_CONFIG` + `AGENTFORGE_LOG_LEVEL` env shortcuts. |
| 7 | Module-side schema integration — `cls.config_schema` convention + `validate_module_configs(cfg, strict=)` walking `modules.*` blocks. |
| 8-10 | `agentforge config validate` (lenient by default, `--strict-modules` to reject missing); `agentforge config show [--resolved \| --raw]`; `agentforge config schema` (JSON Schema export). |
| 11 | This Implementation section + Runbook + CHANGELOG + roadmap + forward-ref sweep. |

### Deviations from this spec

- **Breaking YAML change**: `agent.budget_usd: float` is gone;
  `agent.budget: BudgetConfig` (nested `usd`, `max_tokens`,
  `error_streak_limit`) is the replacement. The schema uses
  `extra="forbid"` so the old flat field reports cleanly at
  `agentforge config validate`. The runtime
  `Agent(budget_usd=, max_iterations=)` kwargs (locked under
  feat-001) are unchanged.
- **Evaluator string-shorthand** `- faithfulness` mentioned in
  spec §4.1 is not implemented. The YAML must spell out
  `- name: faithfulness`. Normalising the bare-string form to
  `EvaluatorEntry(name=..., config={})` is a small loader follow-
  up; the runtime cost is zero (constructed graders work
  identically).
- **`Resolver` lateness**: `agentforge_core.config.module_schemas`
  imports `Resolver` lazily inside `validate_module_configs` to
  avoid a load-order cycle with the values / contracts modules
  the resolver pulls in transitively. Documented inline.
- **`agentforge config schema` JSON output is the standard
  Pydantic v2 `model_json_schema()` shape** — Draft 2020-12. The
  spec's §7 mentioned snapshot testing for the export; we ship
  the dynamic emitter and leave snapshot tests to consumers (the
  schema changes on every minor that touches the root model).

### What's *not* yet implemented

- **Evaluator string-shorthand** normalisation (see above).
- **Auto-wiring** of `modules.memory`, `modules.evaluators`,
  `modules.observability` etc. into `Agent.__init__`. The schema +
  resolver are ready; `Agent.__init__` still expects constructed
  instances via kwargs. The follow-up is small (~50 lines) and
  belongs alongside the destructive CLI (`agentforge add module`)
  in the feat-010 / feat-012 sub-feat that comes next.
- **`agentforge config migrate`** (future spec §5).
- **TypeScript port** of the whole feat-012 surface.

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented "how do I…" content. This is the canonical
home for the feature's runbook; feat-011 / feat-019 consume these
sections into scaffolded agent projects.

### How do I write a minimal `agentforge.yaml`?

```yaml
# ./agentforge.yaml
agent:
  model: "bedrock:us.anthropic.claude-sonnet-4-5-20250929"
  budget:
    usd: 5.0
  max_iterations: 50

logging:
  level: "INFO"
  format: "text"
```

`Agent()` (no args) reads `./agentforge.yaml` automatically. Pass
`config_path=` to point at a different file, or set
`AGENTFORGE_CONFIG=path/to/file.yaml`.

### How do I add modules?

```yaml
modules:
  memory:
    driver: postgres
    config:
      dsn: "${POSTGRES_DSN}"

  evaluators:
    - name: faithfulness
      config:
        sources_field: "retrieved_docs"
    - name: geval
      config:
        rubric: "code-review-correctness"
        cost_cap_usd: 0.20

  observability:
    - name: otel
      config:
        endpoint: "http://otel-collector:4317"
```

Each module's `config:` block is validated against the module's
own Pydantic schema when you run `agentforge config validate` (or
when feat-012's Agent auto-wiring follow-up lands).

### How do I interpolate environment variables?

| Syntax | Behaviour |
|---|---|
| `${VAR}` | required — load fails if `VAR` is unset |
| `${VAR:default}` | optional with a fallback |
| `${VAR:?error message}` | required with a custom error |
| `$$` | literal `$` |

```yaml
agent:
  model: "${MODEL:bedrock:us.anthropic.claude-sonnet-4-5-20250929}"
modules:
  memory:
    driver: postgres
    config:
      dsn: "${POSTGRES_DSN:?Set POSTGRES_DSN for production}"
```

### How do I use per-environment overlays?

Write a base `agentforge.yaml` with defaults, then an overlay
next to it:

```yaml
# agentforge.yaml — defaults
agent:
  budget:
    usd: 1.0
modules:
  memory:
    driver: sqlite
    config:
      path: "./agent.db"
```

```yaml
# agentforge.production.yaml — production overlay
agent:
  budget:
    usd: 50.0
modules:
  memory:
    driver: postgres
    config:
      dsn: "${POSTGRES_DSN}"
```

Then set `AGENTFORGE_ENV=production`. Dict values **deep-merge**;
list values **replace** wholesale (no append). Missing overlays
load silently — `AGENTFORGE_ENV=ci` without a corresponding file
just uses the base.

### How do I override a value from the CLI?

```bash
agentforge config show --override agent.budget.usd=10 \
                       --override logging.level=DEBUG
```

Values are YAML-parsed, so bools / floats / inline lists work:

```bash
agentforge config show --override logging.run_id_filter=false \
                       --override agent.tools='[web_search, calculator]'
```

Overrides apply **after** env-var interpolation and the env-overlay
merge — they win.

### How do I validate my config?

```bash
agentforge config validate
```

Prints `OK` on success; reports each Pydantic error with its YAML
path on failure:

```
agentforge.yaml validation failed:
  agent.budget_usd: Extra inputs are not permitted
```

By default validation is **lenient** on missing modules — useful
for validating a config in CI that references modules installed
elsewhere. Use `--strict-modules` to fail when a referenced module
isn't installed in the active venv.

### How do I see the resolved config?

```bash
agentforge config show           # post-interpolation YAML
agentforge config show --raw     # pre-interpolation YAML
```

`--resolved` (the default) shows the exact config the runtime
will see — env vars expanded, overrides applied, defaults
populated. Useful for "what is the budget actually set to in
production?" Combine with `--env production`:

```bash
AGENTFORGE_ENV=production agentforge config show | grep -A2 budget
```

### How do I enable IDE autocomplete for `agentforge.yaml`?

Generate the JSON Schema and feed it to your editor's YAML
schema setting (or SchemaStore-style YAML language server):

```bash
agentforge config schema > agentforge-schema.json
```

VS Code with the Red Hat YAML extension reads it via:

```jsonc
// .vscode/settings.json
{
  "yaml.schemas": {
    "./agentforge-schema.json": "agentforge.yaml"
  }
}
```

### How do I ship a config schema with my own module?

Declare `config_schema: ClassVar[type[BaseModel]]` on your module
class:

```python
from agentforge_core import register
from pydantic import BaseModel, ConfigDict

class MyDriverConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    dsn: str
    pool_size: int = 5

@register("memory", "mydriver")
class MyDriver:
    config_schema: type[BaseModel] = MyDriverConfig
    def __init__(self, *, dsn: str, pool_size: int = 5) -> None:
        ...
```

Now `agentforge config validate` checks any
`modules.memory.driver: mydriver` block's `config:` against
`MyDriverConfig`. Modules without `config_schema` accept any dict
(backwards-compatible — every shipped module that doesn't declare
one keeps working).

### How do I switch log level without editing the file?

```bash
AGENTFORGE_LOG_LEVEL=DEBUG python my_agent.py
```

The env var is applied **post-validation** to `cfg.logging.level`,
so it works regardless of the file's value.

### When should I NOT use the YAML config?

- **For secrets in the file**: don't. Use `${VAR}` interpolation
  pointing at env vars; the pre-commit hook flags suspected
  secret strings.
- **For Jinja templating**: not supported. Logic in YAML is a P5
  (configuration-is-data) violation. Express logic in Python.
- **For dynamic imports** (`module.factory.path`-style strings):
  not supported by design. Use entry points (feat-010) +
  `@register` for module wiring.
