# feat-012: Configuration system

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-012 |
| **Title** | Configuration — `agentforge.yaml` schema, env interpolation, validation, dotted overrides |
| **Status** | proposed |
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
