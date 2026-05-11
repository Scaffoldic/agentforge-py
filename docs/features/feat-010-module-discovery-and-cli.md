# feat-010: Module discovery & resolution

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-010 |
| **Title** | Module system — entry-point discovery, resolver, `agentforge add/swap/remove` CLI |
| **Status** | shipped (Python — runtime + read-only `list` CLI; destructive `add/swap/remove` deferred to a follow-up alongside feat-012) |
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

---

## Implementation status

**Status: shipped (Python — runtime + read-only `list` CLI).**
Landed across 3 chunks on `feat/010-module-discovery`. The
destructive CLI commands (`add`, `swap`, `remove`) have a hard
dependency on feat-012 (Configuration system) for manifest-driven
config edits + per-module config-schema validation, so they're
deferred to a follow-up sub-feat that lands alongside / right
after feat-012.

| Chunk | Scope |
|---|---|
| 1 | `ModuleInfo` frozen value type + `agentforge_core/resolver/discover.py` (entry-point scanner, lazy + cached); `Resolver.list_installed`; auto-trigger on first `resolve()`. |
| 2 | `agentforge.cli` subpackage (argparse-based, no third-party deps); `agentforge list modules` command with `--category` + `--json`; `[project.scripts]` registration. |
| 3 | This Implementation section + Runbook + CHANGELOG + roadmap + forward-ref sweep. |

### Deviations from this spec

- **Single PR scope is runtime + read-only `list` CLI only.** Spec
  §4.1 shows `agentforge add module ...`, `agentforge swap ...`,
  `agentforge remove ...`. Those three commands manipulate
  `agentforge.yaml`, apply per-module manifest files, validate
  config against each module's `config_schema`, and shell out to
  `pip install`. All of that depends on feat-012 (Configuration
  system) — without it, the manifest format and config-schema
  validation can't be specified cleanly. So this PR ships the
  read-only half; the destructive half lands once feat-012 does.
- **`Resolver.list_available()` not shipped.** Spec §4.2 lists it
  as querying PyPI. Defer — needs an HTTP client + caching
  strategy + offline-mode handling that's better designed in
  isolation when there's a real consumer. The CLI's `agentforge
  list modules --available` is therefore also deferred.
- **`Resolver.clear()` no longer resets discovery.** Empties the
  registry only; tests opt in to a fresh scan via
  `reset_discovery()`. Old behaviour would have broken tests that
  rely on import-time `@register` decorators (e.g. strategies)
  whose registrations are lost forever after a clear.

### What's *not* yet implemented

- **`agentforge add module X`** — `pip install` + manifest apply.
- **`agentforge swap memory sqlite postgres`** — diff + apply.
- **`agentforge remove module X`** — symmetric removal.
- **Manifest format** (`manifest.yaml` per module) — spec lives
  alongside feat-012.
- **`Resolver.list_available()`** — PyPI catalogue query.
- **`agentforge list modules --available`** — pairs with the
  above.
- **Entry-point cache invalidation on pip install/uninstall**
  (spec §8) — current implementation caches per-process; restart
  the process to pick up newly-installed modules.
- **TypeScript port** of the resolver + CLI.

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented "how do I…" content. This is the canonical
home for the feature's runbook; feat-011 / feat-019 consume these
sections into scaffolded agent projects.

### How do I see which modules are installed?

```bash
$ agentforge list modules

EVALUATORS
  correctness                   (agentforge-eval-geval 0.0.0)
  faithfulness                  (agentforge-eval-geval 0.0.0)
  ...
MEMORY
  sqlite                        (agentforge-memory-sqlite 0.0.0)
  ...
PROVIDERS
  bedrock                       (agentforge-bedrock 0.0.0)
```

Use `--category` to narrow the view:

```bash
agentforge list modules --category evaluators
```

Use `--json` for machine-readable output (useful for piping into
`jq` or for scripts that need to enforce "these specific modules
must be installed"):

```bash
agentforge list modules --json | jq '.[] | .name'
```

### How do I make my own module discoverable?

Register it via an entry point in your distribution's `pyproject.toml`:

```toml
[project.entry-points."agentforge.providers"]
mycorp = "mypkg.client:MyCorpClient"

[project.entry-points."agentforge.tools"]
mycorp_lookup = "mypkg.tools:lookup"
```

The group name follows `agentforge.<category>` — categories the
framework knows are: `providers`, `embeddings`, `memory`, `graph`,
`vector_stores`, `strategies`, `tools`, `evaluators`, `hooks`,
`renderers`, `protocols`. (Custom categories work too; you'll
just need to teach your own `Resolver.resolve(category, name)`
callers about them.)

`pip install mypkg` makes the class show up under
`agentforge list modules` and resolvable via
`Resolver.global_().resolve("providers", "mycorp")` — no explicit
import needed.

For in-repo classes that aren't distributed as a package, use the
`@register` decorator instead:

```python
from agentforge_core import register

@register("hooks", "my-statsd")
class MyStatsdHook:
    ...
```

`@register` fires at import time, so the calling code must import
the module containing the decorator at least once for the
registration to take effect.

### How do I find which package shipped a module?

`Resolver.list_installed(category=None)` returns `ModuleInfo`
records:

```python
from agentforge_core import Resolver

for m in Resolver.global_().list_installed(category="evaluators"):
    print(f"{m.name}: {m.package} {m.version}")
# correctness: agentforge-eval-geval 0.0.0
# ...
```

`ModuleInfo` fields: `category`, `name`, `package` (distribution
name; `None` for `@register`-only classes), `version`,
`cls_qualname` (fully-qualified class name for diagnostics).

### How do I debug "module not found at startup"?

The resolver raises `ModuleError` with a remediation hint:

```
ModuleError: No module registered for memory:'postgres'.
Registered memory: ['sqlite']. Install the relevant agentforge-*
package or register a custom class with @register('memory', 'postgres').
```

If your package IS installed but the resolver doesn't see it,
check:

1. **Entry-point name match.** Does `pyproject.toml`'s
   `[project.entry-points."agentforge.memory"]` table list the
   exact name you're asking for? Run `agentforge list modules`
   to see what the resolver found.
2. **Package actually installed in this venv.** `uv pip show
   <package>` confirms.
3. **Class load failure.** The resolver logs at WARN via the
   `agentforge.resolver` logger when an entry point's `.load()`
   raises; check your logs.
4. **Class is actually a class.** Entry points pointing at a
   function or instance get skipped with a WARN.

### How do I write a module that ships with manifest + default config?

**Not yet supported in this PR.** The `manifest.yaml` format and
`agentforge add module X` workflow ship in a follow-up sub-feat
alongside feat-012 (Configuration system). For now, document the
config block your module expects in your README; consumers paste
it into `agentforge.yaml` manually.

### When should I NOT rely on entry-point discovery?

- **Inside hot paths.** Discovery runs once on first
  `Resolver.resolve()` / `list_*` per process. It's fast (sub-
  millisecond on typical workspaces) but not free. The runtime
  pays it once.
- **For circular registrations.** If module A's entry point
  imports module B, and B imports A, the entry-point loader
  raises during discovery and the resolver logs WARN and skips.
  Restructure your imports.
- **For dynamic registrations from non-importable paths.** Use
  `@register` from a module that gets imported by the agent code,
  not entry points.
