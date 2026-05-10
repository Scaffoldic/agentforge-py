# feat-010: Module discovery & resolution

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-010 |
| **Title** | Module system — entry-point discovery, resolver, `agentforge add/swap/remove` CLI |
| **Status** | proposed |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.2 |
| **Languages** | both |
| **Module package(s)** | `agentforge-core` (resolver), `agentforge` (CLI) |
| **Depends on** | feat-001, feat-012 |
| **Blocks** | feat-011 (uses manifest format) |

---

## 1. Why this feature

The whole "plug-and-play" story collapses without a way to actually plug
modules in. A user installs `agentforge-memory-postgres`. What happens next?
Without a discovery mechanism, the answer is "import it manually, write
factory code, edit your wiring." With a discovery mechanism, the answer is
"the resolver finds it; you reference it by name in YAML."

The pain we are removing: every framework that has tried to be modular has
either skipped this layer (forcing users to wire modules by hand) or built
it badly (dynamic imports of arbitrary paths, fragile subclass-and-pray).
Both lead to "module installed but not used" footguns.

## 2. Why it must ship as framework

- **A consistent registration mechanism is the *whole* value.** If each
  module type has its own registration path, the `pip install` + YAML
  flow breaks.
- **Static inspectability is non-negotiable.** `agentforge list modules`
  must enumerate everything the runtime *will* load, before any user code
  runs. That's only possible with framework-owned discovery.
- **CLI commands** (`add`, `swap`, `remove`) are agent-agnostic — they
  manipulate config and call pip. Framework owns them; agents inherit
  the UX.
- **Fail-at-startup (P11)** depends on the resolver checking *everything*
  at agent construction. That requires the framework controlling which
  modules to load and how.
- **Without framework ownership:** ad-hoc imports, brittle wiring, no
  catalogue, no guarantee that a module declared in YAML is actually
  installed.

## 3. How derived agents benefit

- **`pip install agentforge-X` + YAML edit = working module.** No imports,
  no factory code.
- **`agentforge list modules`** shows what's available right now and what
  could be installed (queries PyPI metadata).
- **`agentforge add module memory-postgres`** does the install + config
  edit + boilerplate scaffold in one command.
- **`agentforge swap memory sqlite postgres`** atomically updates the
  config, installs the new driver, runs migrations, and prints the final
  diff.
- **Custom modules are first-class.** Add an entry point to your own pyproject;
  the resolver finds your driver alongside framework-shipped ones.
- **No module surprises in production.** If the YAML references a module
  that's not installed, the agent fails at startup with a clear message,
  not at hour 2 of a run.

## 4. Feature specifications

### 4.1 User-facing experience

```bash
$ agentforge list modules
INSTALLED
  providers     anthropic, bedrock, openai          (agentforge-anthropic 0.2.1, ...)
  memory        sqlite, postgres                    (agentforge-memory-sqlite 0.2.0, ...)
  strategies    react                               (agentforge 0.2.0)
  tools         web_search, calculator, file_read   (agentforge 0.2.0)

$ agentforge list modules --available
AVAILABLE (queryable on PyPI)
  providers     ollama, gemini, litellm
  memory        surrealdb, neo4j
  strategies    plan-execute, tot, multi-agent
  protocols     mcp, a2a
  observability otel, langfuse, phoenix

$ agentforge add module memory-postgres
  → installing agentforge-memory-postgres ........ 0.2.1
  → reading manifest ............................. ok
  → writing .agentforge-state/manifests/memory-postgres.yaml
  → applying manifest:
      APPENDED  .env.example     (POSTGRES_DSN)
      ADDED     db/migrations/agentforge/0001_init.sql
      MODIFIED  agentforge.yaml  (modules.memory)
  → done.
  Next: set POSTGRES_DSN, run `agentforge db migrate`.
```

```python
# Programmatic registration (custom module)
from agentforge import register

@register("memory", "my-store")
class MyMemoryStore(MemoryStore):
    ...
```

```toml
# pyproject.toml — entry-point registration
[project.entry-points."agentforge.memory"]
my-store = "mypkg.memory:MyMemoryStore"
```

### 4.2 Public API / contract

```python
# agentforge_core/resolver.py
class Resolver:
    """Discovers and instantiates modules by category + name."""

    def resolve(self, category: str, name: str) -> type: ...
    def resolve_with_config(self, category: str, name: str,
                            config: dict[str, Any]) -> Any: ...
    def list_installed(self, category: str | None = None) -> list[ModuleInfo]: ...
    def list_available(self, category: str | None = None) -> list[ModuleInfo]: ...

class ModuleInfo(BaseModel):
    category: str
    name: str
    package: str
    version: str
    config_schema: type[BaseModel] | None
    manifest_path: Path | None
    capabilities: set[str]

# Decorator (alternative to entry points for single-agent use)
def register(category: str, name: str) -> Callable[[type], type]: ...
```

**Categories (entry-point groups):** `agentforge.providers`,
`agentforge.memory`, `agentforge.graph`, `agentforge.strategies`,
`agentforge.tools`, `agentforge.evaluators`, `agentforge.hooks`,
`agentforge.renderers`, `agentforge.protocols`.

### 4.3 Internal mechanics

```
Startup sequence (Agent.__init__):

  1. Resolver scans `importlib.metadata.entry_points()` for all groups
     starting with `agentforge.*`. Builds a flat map { (category, name) → class }.
  2. Reads agentforge.yaml + constructor kwargs to determine which modules
     are active.
  3. For each active module:
       a. Look up class in the map (fail loudly if missing).
       b. If module declares config_schema, validate raw config dict.
       c. Instantiate with validated config.
  4. Wire instantiated modules into Agent.

CLI flows (agentforge add module X):

  1. Run `pip install agentforge-X` in the project venv.
  2. Read package metadata to find manifest.yaml.
  3. Apply manifest:
       - Insert env-var entries into .env.example (idempotent).
       - Copy `templates/` files into project (with marker headers).
       - Insert default config block into agentforge.yaml.
       - Update .agentforge-state/manifests/X.yaml.
  4. Print next-steps (env vars to set, commands to run).
```

### 4.4 Module packaging

`agentforge-core` ships the resolver. `agentforge` ships the CLI commands.
Every other module ships at minimum (a) a registered class via entry point,
(b) a Pydantic config schema, (c) a `manifest.yaml`. (See
[`module-system.md`](../design/module-system.md) §4.3.)

### 4.5 Configuration

```yaml
modules:
  memory:
    driver: postgres                  # resolver looks up agentforge.memory.postgres
    config:                           # validated against driver's schema
      dsn: "${POSTGRES_DSN}"
      project: "my-agent"

  observability:
    - name: otel
      config:
        endpoint: "http://localhost:4317"

  protocols:
    - name: mcp
      config:
        servers:
          - command: "npx -y @modelcontextprotocol/server-fs"
```

## 5. Plug-and-play & upgrade story

This *is* the plug-and-play story. See feat-011 for the upgrade story (which
uses the same manifest mechanism).

## 6. Cross-language parity

Python uses `importlib.metadata` entry points. TS uses `package.json`
`agentforge` field — modules declare entries the same way. CLI commands
identical. Manifest format identical.

## 7. Test strategy

- **Resolver:** registered modules discoverable; missing → clean error;
  duplicate registration → clean error.
- **Manifest application:** idempotent (running twice doesn't duplicate
  env-var entries).
- **Pip install side effects isolated:** `add module` runs pip in the
  active venv; never global.
- **Cross-platform CLI:** Linux, macOS, Windows; manifest path-handling.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Slow startup with many entry points | Cache the entry-point scan; invalidate on `pip install/uninstall` (file-mtime check on site-packages) |
| Manifest format Python vs YAML | YAML for declarative manifests; rare `post_install_hook.py` for genuine procedural needs |
| Pip install during `add module` mutates the lockfile | Document; recommend committing the lockfile after `add module` |
| Custom modules without entry points (single-agent code) | `@register` decorator path; works for in-repo modules without publishing |
| Conflict resolution if two modules register the same name | Resolver fails at startup with the conflicting package list |

## 9. Out of scope

- A package marketplace. PyPI / npm are the registries.
- Hot reloading of modules at runtime. Restart-to-change.
- Sandboxed module execution. Modules run with full process privileges;
  package trust is the boundary.

## 10. References

- [`module-system.md`](../design/module-system.md) — full design
- [`design-principles.md`](../design/design-principles.md) — P1, P2, P5, P11
- feat-001, feat-011, feat-012, feat-017
