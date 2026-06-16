---
status: fixed in 0.3.0
severity: P2
found-in: 0.2.4
found-via: dogfooding (README demo gif)
---

# bug-022 — `modules.memory` can't be built from config: every real backend fails through the CLI

## Symptom

Configuring a memory backend in `agentforge.yaml` and running any CLI
command that builds it (`agentforge run`, `health`, `db migrate`,
`debug`, or `run --replay`) fails before the agent starts:

```
$ agentforge run "hi" --config agentforge.yaml   # modules.memory: {driver: sqlite, config: {path: mem.sqlite}}
SqliteMemoryStore.__init__() got an unexpected keyword argument 'path'
```

The same `TypeError` shape occurs for postgres / neo4j / surrealdb
(`unexpected keyword argument 'dsn'` / `'url'`). Configured memory is
effectively unusable from the CLI for **every** real backend.

## Reproduction

```python
from agentforge_core.config.schema import AgentForgeConfig
from agentforge.cli._build import build_memory_from_config

cfg = AgentForgeConfig.model_validate({
    "agent": {"model": "anthropic:claude-sonnet-4-5", "strategy": "react"},
    "modules": {"memory": {"driver": "sqlite", "config": {"path": ":memory:"}}},
})
build_memory_from_config(cfg)   # TypeError: __init__() got an unexpected keyword argument 'path'
```

The gap went unnoticed because the shipped example configs and the
scaffold templates never populate `modules.memory` — the agent falls
back to the in-process `InMemoryStore`, which sidesteps the builder.

## Root cause

`build_memory_from_config` (in
`packages/agentforge/src/agentforge/cli/_build.py`) instantiated the
resolved store via the shared **sync** `_instantiate(cls, cfg)`, whose
final fallback is `cls(**cfg)`.

But every real memory backend constructs **asynchronously** and via a
named factory, not its bare constructor:

| backend | factory | `__init__` wants |
|---------|---------|------------------|
| sqlite | `async from_path(path)` | `connection` |
| postgres | `async from_dsn(dsn, …)` | `runner` |
| neo4j | `async from_url(url, *, auth, …)` | `runner` |
| surrealdb | `async from_url(url, *, …)` | `runner` |

None implemented the `from_config` factory convention that **every
other module type already has** — LLM clients (`AnthropicClient`,
`OpenAIClient`, …), embedders, rerankers, observability hooks, and
protocol bridges all expose `from_config`. The memory stores were the
sole module type missing it, so `_instantiate` fell through to
`cls(**cfg)` and passed the YAML keys straight to a constructor that
doesn't accept them.

## Fix

Implement the missing convention as an **async** `from_config` on each
store (memory construction opens a connection, so unlike the sync
`from_config` on stateless modules it must be a coroutine), and give
memory a dedicated async build path in `_build.py`:

1. **`from_config` on each store** (delegates to the existing async
   factory), e.g. sqlite:

   ```python
   @classmethod
   async def from_config(cls, *, path: str | Path) -> SqliteMemoryStore:
       return await cls.from_path(path)
   ```

   postgres → `from_dsn`, neo4j/surrealdb → `from_url` (coercing the
   YAML `auth` list to the `tuple[str, str]` they expect).

2. **`_ainstantiate_memory(cls, cfg)`** in `_build.py` — prefers an
   awaitable `from_config` (`await`s it), falling back to the shared
   sync `_instantiate` so a sync-constructed store/double still loads.

3. **`build_memory_from_config` becomes `async`**; its five callers
   (`build_agent_from_config`, `run_cmd`, `health_cmd`, `db_cmd`,
   `debug_cmd`) are all already in async contexts and now `await` it.
   `health`'s generic `_probe` awaits the factory result when it's
   awaitable.

The shared sync `_instantiate` and the other five `build_*_from_config`
helpers are untouched — only memory routes through the async path, so
no other module type regresses.

This is implementing an established convention, not a new design
decision, so no ADR accompanies it.

## Verification

- Regression test (offline, real sqlite) in
  `packages/agentforge/tests/unit/test_cli_build.py`:
  `test_build_memory_builds_real_sqlite_store_from_config` configures
  `modules.memory: {driver: sqlite, config: {path: ":memory:"}}`,
  `await`s `build_memory_from_config`, and asserts a live
  `SqliteMemoryStore` with a working `put`/`get` round-trip. This test
  fails (`TypeError`) on the pre-fix code.
- The two previously-sync builder tests are converted to async + the
  `_FakeMemory` (sync, no `from_config`) test exercises the sync
  fallback branch of `_ainstantiate_memory`.
- `SqliteMemoryStore.from_config` has its own offline unit test
  (`packages/agentforge-memory-sqlite/tests/unit/test_memory.py::test_from_config_builds_a_live_store`).
- postgres / neo4j / surrealdb `from_config` are `# pragma: no cover`
  (live-only), matching the existing convention for the live factories
  on those backends.
- `uv run pre-commit run --all-files` green (ruff, mypy --strict,
  bandit, coverage ≥ 90%).

## Notes

- This bug is *why* the README demo gif couldn't show `agentforge run
  --replay` offline: `--replay` rebuilds the recording's store via
  `build_memory_from_config`, which threw before it could read the
  recording. With this fix, a sqlite-backed recording can be replayed
  offline (the gif work is a separate follow-up).
- Discovered while dogfooding the framework to build the README demo —
  a class of failure that only a configured-memory CLI path triggers,
  and no shipped config exercised it.
