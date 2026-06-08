# Design Doc: AgentForge module system

## Metadata

| Field | Value |
|---|---|
| **Title** | Module system — pick-and-choose, install-later, upgrade-safe |
| **Status** | draft |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Last updated** | 2026-05-09 |
| **Supersedes** | none |
| **Superseded by** | none |
| **Related features** | feat-001 (core), feat-010 (module CLI), feat-011 (scaffolding & upgrade) |

---

## 1. Context

AgentForge's central promise: a developer picks the modules they need today, and
adds modules for new requirements later — without rewriting their agent and without
breaking on framework upgrades.

Concrete scenarios this design must support:

- **Scenario A — DB added later.** A developer scaffolds an agent with no
  persistence. Three months later, they realise they want SurrealDB. They run one
  CLI command; the framework installs the module, scaffolds the boilerplate (env
  vars, migration files, wiring code), and the rest of their agent code is
  untouched.
- **Scenario B — MCP added later.** Same shape. `agentforge add module mcp`. The
  agent now exposes its tools as MCP servers and consumes other MCP tools, with no
  manual integration code.
- **Scenario C — DB swap.** SQLite → Postgres. Same `MemoryStore` ABC; new driver;
  developer config edit; no business-logic change.
- **Scenario D — Framework upgrade.** Framework moves from 0.4 → 0.5. Some
  scaffolded files have new defaults. `agentforge upgrade` applies the diff using
  Copier-style three-way merge; developer's customisations survive.

Every other agent framework today supports *some* of these (some support A and C via
constructor swap; some support A via tool-extras; some support A via slim-extras).
**None** support all four with a single coherent mechanism. That is what this
design covers.

## 2. Goals

- A module is a single pip install away. No private registry. No manual import
  wiring. No editing of framework-owned files.
- The same mechanism handles LLM providers, persistence drivers, evaluators,
  observability, MCP, and future categories we haven't named yet.
- The agent's `agentforge.yaml` is the single source of truth for which modules
  are active and how they are configured.
- An agent can be safely upgraded across minor framework versions without breaking
  custom code.
- The module-resolution path is statically inspectable: I can run a command and see
  every module that will load, with version, package source, and config keys.

## 3. Non-goals

- Hot-reloading / runtime swapping of modules. Modules are wired at agent
  construction; restarts are required to change them.
- Module sandboxing. Modules are pip packages — they run with full Python
  privileges. We rely on package trust, not runtime isolation.
- Cross-version-compatibility of *modules* with each other. Each module pins its
  `agentforge-core` major version; conflicts are surfaced by pip's resolver.
- A plugin marketplace UI. Out of scope until the module catalogue is stable.

## 4. Proposal

### 4.1 The four pieces of the mechanism

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │ 1. PACKAGE                                                          │
   │    A normal pip package on PyPI / npm.                              │
   │    Naming: agentforge-<category>-<provider>                         │
   │    Examples: agentforge-anthropic, agentforge-memory-postgres       │
   └────────────────────────────┬────────────────────────────────────────┘
                                │ declares
                                ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │ 2. ENTRY POINT (declared in pyproject.toml / package.json)          │
   │                                                                     │
   │    [project.entry-points."agentforge.providers"]                    │
   │    anthropic = "agentforge_anthropic:AnthropicClient"               │
   │                                                                     │
   │    [project.entry-points."agentforge.memory"]                       │
   │    postgres = "agentforge_memory_postgres:PostgresMemoryStore"      │
   │                                                                     │
   │    Categories: providers · memory · graph · tools · evaluators ·    │
   │                strategies · hooks · renderers                       │
   └────────────────────────────┬────────────────────────────────────────┘
                                │ discovered at startup
                                ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │ 3. CONFIG (agentforge.yaml)                                         │
   │                                                                     │
   │    agent:                                                           │
   │      model: "anthropic:claude-sonnet-4.7"   # ← provider:id syntax  │
   │      strategy: "react"                                              │
   │    modules:                                                         │
   │      memory:                                                        │
   │        driver: "postgres"                                           │
   │        config:                                                      │
   │          dsn: "${POSTGRES_DSN}"                                     │
   │      mcp:                                                           │
   │        servers:                                                     │
   │          - name: "filesystem"                                       │
   │            command: "npx -y @modelcontextprotocol/server-fs"        │
   └────────────────────────────┬────────────────────────────────────────┘
                                │ resolved by
                                ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │ 4. RESOLVER (agentforge-core, runs at Agent construction)           │
   │    For each modules.* entry:                                        │
   │      1. Look up entry point by category + driver name               │
   │      2. Validate config against the driver's Pydantic schema        │
   │      3. Instantiate driver with the validated config                │
   │      4. Wire it into Agent                                          │
   │    Failures here raise at startup (P11), never mid-run.             │
   └─────────────────────────────────────────────────────────────────────┘
```

### 4.2 The CLI surface

```bash
# discover
agentforge list modules               # what's installed and registered
agentforge list modules --available   # what could be installed (queries PyPI metadata)

# add (scenario A & B)
agentforge add module memory-postgres
   ↳ runs: pip install agentforge-memory-postgres
   ↳ inserts a `modules.memory` block into agentforge.yaml with sane defaults
   ↳ scaffolds any boilerplate the module needs (env vars in .env.example,
     migration files in db/migrations/, etc.)
   ↳ prints next steps

agentforge add module mcp
   ↳ same flow, but writes a `modules.mcp.servers: []` skeleton

# swap (scenario C)
agentforge swap memory sqlite postgres
   ↳ pip install agentforge-memory-postgres
   ↳ rewrites the modules.memory block to point at postgres
   ↳ runs the postgres driver's migration command
   ↳ prints how to run a one-off data migration script

# remove
agentforge remove module memory-postgres

# upgrade (scenario D)
agentforge upgrade                    # bumps framework + applies template diff
```

### 4.3 What boilerplate does a module own?

A module ships **three** things in its package:

1. **The implementation class** — registered via entry point.
2. **A Pydantic / Zod config model** — describes the keys the module reads from
   `modules.<category>` and validates them. Resolver uses this for fail-at-startup
   validation (P11).
3. **A `manifest.yaml`** — declarative description of any boilerplate the module
   requires the developer's project to have. The CLI reads this and applies it
   when the module is added.

```yaml
# agentforge_memory_postgres/manifest.yaml
name: agentforge-memory-postgres
category: memory
driver: postgres

config_schema: agentforge_memory_postgres.config:PostgresMemoryConfig

requires:
  env_vars:
    - name: POSTGRES_DSN
      example: "postgresql+asyncpg://user:pass@localhost:5432/agent"
  files:
    - source: templates/migrations/0001_init.sql
      dest: db/migrations/0001_agentforge_memory_init.sql
      writeable: false                # marker file: do not edit
    - source: templates/.env.snippet
      dest: .env.example
      mode: append-if-missing
  commands_after_install:
    - "agentforge db migrate"
```

When `agentforge add module memory-postgres` runs, the CLI:

- Installs the pip package
- Reads the manifest
- Adds env vars to the project's `.env.example` (if not already there)
- Copies migration files into `db/migrations/` with the AgentForge marker header
- Updates `agentforge.yaml`
- Prints the post-install command list

### 4.4 The marker header (why upgrades don't break custom code)

Every file the framework or a module copies into a developer's project starts with
a marker comment:

```sql
-- AGENTFORGE-MANAGED: do not edit. To customise, run `agentforge fork <file>`.
-- Module: agentforge-memory-postgres
-- Version: 0.5.1
-- Hash: 9f3a...
```

`agentforge upgrade` only touches files with the marker AND a matching hash. If a
developer has edited a managed file, the upgrade reports a conflict and walks them
through `agentforge fork` (which removes the marker, claiming ownership of the
file). After fork, the file is the developer's; future upgrades skip it.

### 4.5 String identifiers and the resolver

The string-identifier syntax for picking a driver is a hard convention:

| Slot | Syntax | Resolves to |
|---|---|---|
| Model | `"anthropic:claude-sonnet-4.7"` | `agentforge.providers.anthropic` entry point with model id |
| Strategy | `"react"` / `"plan-execute"` | `agentforge.strategies.react` entry point |
| Memory | `modules.memory.driver: "postgres"` | `agentforge.memory.postgres` entry point |
| Tool | `tools: ["web_search", "calculator"]` | `agentforge.tools.<name>` entry points |

A developer can always bypass the string by passing a typed instance:

```python
from agentforge_anthropic import AnthropicClient
agent = Agent(llm=AnthropicClient(...))   # explicit, escape hatch
```

This avoids the meta-provider error-swallowing anti-pattern (research notes,
section 3) — when something goes wrong, the developer can drop to typed objects and
get a clean stack trace.

### 4.6 Module categories at v0.x

| Category | Entry-point group | Example drivers |
|---|---|---|
| LLM provider | `agentforge.providers` | `anthropic`, `bedrock`, `openai`, `litellm`, `ollama` |
| Memory store | `agentforge.memory` | `sqlite`, `postgres`, `surrealdb` |
| Graph store | `agentforge.graph` | `surrealdb`, `neo4j` |
| Reasoning strategy | `agentforge.strategies` | `react`, `plan-execute`, `tot`, `multi-agent` |
| Tool | `agentforge.tools` | `web_search`, `calculator`, `file_read`, `shell`, plus user tools |
| Evaluator | `agentforge.evaluators` | `faithfulness`, `groundedness`, `consistency`, `geval` |
| Observability hook | `agentforge.hooks` | `otel`, `langfuse`, `phoenix` |
| Renderer | `agentforge.renderers` | `scorecard`, `narrative`, `completion` |
| Protocol | `agentforge.protocols` | `mcp`, `a2a` |

New categories require a design doc (P1, P12).

## 5. Alternatives considered

| Option | Why we didn't pick it |
|---|---|
| Vendoring module source into the agent (the vendored-framework-code model) | Fails P8; upgrades require manual diff every time. The audit benefit is real but the upgrade cost is higher than the audit benefit for our target users. |
| Single mega-package with all modules included (`agentforge[full]`) | Bloats install size; pulls in every SDK; defeats the point of opt-in modules. We *do* offer `agentforge[full]` as a convenience extra, but the underlying split is real. |
| Plugin loading from arbitrary file paths | Fails P5; turns config into code; opens an attack surface. |
| String-only identifiers (no escape hatch to typed clients) | A known footgun. Always allow passing a typed instance. |
| Module hot-reload | Out of goals; complicates the resolver enormously. Restart-to-change is fine for an agent runtime. |

## 6. Migration / rollout

This is a v0.1 design; there is nothing to migrate from in AgentForge. A predecessor
project's agents could be migrated with a future `agentforge migrate` importer (provided
by feat-011 once it lands), which reads the predecessor's `cookiecutter` answer file and
produces an equivalent `agentforge.yaml`.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Module catalogue sprawls (version-matrix sprawl) | Coordinate releases; require two real users before new module category |
| Manifest drift across modules | Conformance test that loads every published module's manifest and validates schema |
| Marker-header collisions with developer formatters | Markers are syntactically valid comments in every target language; pre-commit verifies marker integrity |
| Entry-point resolution slow on large installs | Cache the entry-point map at first agent construction; invalidate on `pip install`/`pip uninstall` |
| Developer modifies a managed file silently, upgrade silently overwrites | Hash check at upgrade time; conflict surfaced + `fork` flow required |
| pip-resolved version of `agentforge-core` differs from what a module expects | Each module pins `agentforge-core ~=` to its exact major; pip's resolver fails fast |

## 8. Open questions

1. **Manifest format — YAML vs Python.** YAML is declarative (good) but cannot
   express conditional logic. Python lets a module run code at install time
   (flexible but dangerous). Decision needed before feat-010 implementation. Lean:
   YAML, with a clearly-named `post_install_hook.py` for the rare case it's needed.
2. **Multi-language manifests.** A module that ships both Python and TS halves
   needs a single source of truth. Likely answer: one `manifest.yaml` per
   language-package, both authored from a shared template.
3. **Should `agentforge add module` require a network call?** Could read manifest
   from local cache after first install. Decide once we have the CLI's offline
   story.
4. **Versioning of the manifest schema itself.** A module's `manifest.yaml` should
   declare which manifest-schema version it conforms to, so the CLI can refuse to
   apply manifests it doesn't understand.

## 9. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-09 | Use Python entry points (and `package.json` exports in TS) for discovery | Standard mechanism in both ecosystems; statically inspectable; no dynamic imports |
| 2026-05-09 | One unified `agentforge.yaml` for all modules | Single source of truth beats per-module config files |
| 2026-05-09 | Marker headers + Copier-style upgrade | Solves "upgrade without breaking custom code" requirement directly |

## 10. References

- [`architecture.md`](./architecture.md) — where the module system fits
- [`design-principles.md`](./design-principles.md) — P1, P2, P5, P8, P11, P12 cited above
- [`scaffolding-and-upgrade.md`](./scaffolding-and-upgrade.md) — how `agentforge new` and `agentforge upgrade` work in detail
- [`persistence-and-orm.md`](./persistence-and-orm.md) — concrete example of the module mechanism applied to memory drivers
- [Copier — file regeneration with diff merging](https://copier.readthedocs.io/) — the upgrade mechanism reference
