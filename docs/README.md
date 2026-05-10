# AgentForge — documentation

> **AgentForge** is an open-source, plug-and-play framework for building production
> AI agents. One install, three lines, a working agent. Need persistence? Add a
> module. Need MCP? Add a module. Need to swap SQLite for SurrealDB? Edit one line
> of config and re-run the CLI. Your custom agent code never gets touched.
>
> Available in **Python** (`agentforge`) and **TypeScript** (`agentforge`). Same
> contracts, same module catalogue, idiomatic per language.

---

## Status

This is **v0.x — pre-alpha**. We are designing in the open. Nothing is shipped yet.
The goal of this docs tree is to lock in the design before the code lands.

## The 30-second pitch

```bash
pip install "agentforge[anthropic]"
```

```python
from agentforge import Agent
from agentforge.tools import web_search

agent = Agent(model="anthropic:claude-sonnet-4.7", tools=[web_search])
print(agent("What's the latest on AI agent frameworks?"))
```

That's the whole hello-world. Defaults underneath: ReAct loop, in-memory state,
USD budget cap, run-id propagation, structured logs. None of those are ceremony you
have to write.

Want persistence later? `pip install agentforge-memory-sqlite` and add three lines
to `agentforge.yaml`. The CLI scaffolds the boilerplate and you keep working.

Want to upgrade from `agentforge 0.4` to `0.5` six months later? `agentforge upgrade`
applies the framework's template diff while leaving every file you authored alone.

## What's in this folder

| Path | Purpose |
|---|---|
| [`README.md`](./README.md) | This file — the entry point |
| [`design/`](./design/) | Architecture and cross-cutting design decisions for the framework |
| [`features/`](./features/) | One doc per feature (`feat-NNN-*.md`) — see [`features/README.md`](./features/README.md) for the catalogue |
| [`adr/`](./adr/) | Architecture decision records (MADR / Nygard format) — immutable history of every load-bearing decision |
| [`roadmap.md`](./roadmap.md) | Shipped + backlog pointer (canonical numbering) |

**Note on runbooks.** End-user-facing runbooks (the 16 `docs/runbooks/`
documents that ship inside *generated agent projects*) are authored
in the `agentforge-templates` repo and rendered into projects at
scaffold time. They are not stored under this tree — that would
duplicate them and let them drift. The design and contract for the
runbook system live in feat-019.

Doc templates live at the workspace root under
`/Users/khemchandjoshi/MbytesWorkspace/ai-agents/.claude/templates/`
(shared across all projects in the workspace). Every doc here was
started by copying one of those templates.

## Reading order

### If you are evaluating AgentForge

1. This README.
2. [`design/architecture.md`](./design/architecture.md) — the
   canonical system view.
3. [`features/README.md`](./features/README.md) — the feature
   catalogue.

### If you want to use AgentForge

1. This README.
2. The `agentforge-py/README.md` quickstart at the repo root.
3. [`design/module-system.md`](./design/module-system.md) —
   picking and adding modules.

### If you want to contribute

1. This README.
2. [`../AGENTS.md`](../AGENTS.md) — universal AI rules for this
   project (workflow, branch naming, anti-patterns).
3. [`../.claude/CLAUDE.md`](../.claude/CLAUDE.md) — Claude Code
   reading order.
4. [`design/architecture.md`](./design/architecture.md).
5. [`design/design-principles.md`](./design/design-principles.md) —
   the principles every feature follows.
6. [`design/module-system.md`](./design/module-system.md),
   [`persistence-and-orm.md`](./design/persistence-and-orm.md),
   [`scaffolding-and-upgrade.md`](./design/scaffolding-and-upgrade.md) —
   the three load-bearing design decisions.
7. Pick an open feature in [`features/`](./features/) (status
   `proposed`) and read its doc.

## Project layout

```
agentforge-py/
├── README.md                  quickstart
├── AGENTS.md                  universal AI rules for this project
├── CHANGELOG.md               release notes
├── pyproject.toml             uv workspace root
├── docs/                      ← you are here
│   ├── README.md
│   ├── roadmap.md             shipped + backlog pointer (canonical)
│   ├── design/                architecture + cross-cutting designs
│   ├── features/              feat-NNN-*.md (20 specs + README)
│   └── adr/                   immutable architecture decisions
├── .claude/
│   ├── CLAUDE.md              entry point for AI assistants
│   ├── standards/             coding / testing / git / docs / configuration
│   ├── checklists/            pre-feature / pre-commit / pre-pr / feature-complete
│   └── state/                 current.md, log.md (per-project state)
├── packages/                  uv workspace members
│   ├── agentforge-core/
│   ├── agentforge/
│   ├── agentforge-bedrock/
│   ├── agentforge-memory-sqlite/
│   ├── agentforge-memory-postgres/
│   ├── agentforge-memory-neo4j/
│   └── agentforge-memory-surrealdb/
└── scripts/                   doc + ADR validators (used by pre-commit/CI)
```

The parent workspace at
`/Users/khemchandjoshi/MbytesWorkspace/ai-agents/` hosts only
**workspace-meta** material (the abstract development pipeline,
shared doc templates, the multi-project README). Future sibling
projects — TypeScript port (`typescript/agentforge-ts/`) and agents
built using this framework — sit under the parent workspace as
peers and follow the same self-contained structure.

## What AgentForge is, in one paragraph

A small core (`agentforge-core`) defines the contracts: `Agent`, `ReasoningStrategy`,
`LLMClient`, `EmbeddingClient`, `Tool`, `MemoryStore`, `Evaluator`, `Finding`,
`InputValidator`/`OutputValidator`/`ToolCallGate`, `ChatHistoryStore`. A "batteries"
package (`agentforge`) ships the sane defaults — ReAct loop, in-memory store, simple
findings, four built-in tools, basic safety defaults. Everything else is an opt-in
module: providers (`agentforge-anthropic`, `agentforge-openai`, `agentforge-bedrock`,
`agentforge-voyage`), persistence (`agentforge-memory-sqlite`, `-postgres`,
`-surrealdb`, `-neo4j`), protocols (`agentforge-mcp`, `agentforge-a2a`),
evaluators, observability backends, safety modules
(`agentforge-guard-llmguard`, `-presidio`, `-nemo`, `-llamaguard`), and
deployment shapes (`agentforge-chat` for conversational agents,
`agentforge-chat-http` for chat servers). Modules register themselves via
Python entry points (or `package.json` exports in TS), so a `pip install`
plus an `agentforge.yaml` entry is all it takes to wire one in.

The opinionated parts are the parts you usually have to bolt on yourself in other
frameworks: cost guardrails before every LLM call, run-id propagation across logs,
distributed tracing, cross-provider fallback chains, durable claim records,
evaluator suites with an LLM judge, prompt-injection and PII defenses by default.
Those are defaults you don't see, not ceremony you have to perform.

`Agent` is one-shot by design — `run(task)` → `RunResult`. For chat /
conversational deployments, `ChatSession` (feat-020) wraps `Agent` with
turn history, streaming, multi-tenant isolation, and an HTTP/WebSocket/SSE
server. Same primitives, different deployment shape.

## What AgentForge is not

- A research playground. Stable contracts beat clever abstractions.
- A LangChain replacement. We don't try to be the universal AI toolkit; we ship the
  pieces an agent needs and stop.
- A no-code platform. The audience is Python and TypeScript engineers. We make their
  job easier; we don't try to remove them.
- An attempt at framework-of-everything. Anything tangential — vector store
  abstractions, prompt-template engines, document loaders — belongs in a separate
  library you call from a tool.

## Naming and packaging at a glance

| Layer | Python | TypeScript |
|---|---|---|
| Core ABCs | `agentforge-core` (PyPI) | `@agentforge/core` (npm) |
| Default runtime + prebuilts | `agentforge` (PyPI) | `agentforge` or `@agentforge/runtime` (TBD) |
| Provider extension | `agentforge-anthropic` | `@agentforge/anthropic` |
| Persistence module | `agentforge-memory-postgres` | `@agentforge/memory-postgres` |
| CLI | `agentforge` (binary) | `agentforge` (binary) |

Final TS scoping (`@agentforge/*` vs flat) is open — see `design/architecture.md`.

## Status of design docs at a glance

| Doc | Status |
|---|---|
| [`design/architecture.md`](./design/architecture.md) | draft |
| [`design/design-principles.md`](./design/design-principles.md) | draft |
| [`design/module-system.md`](./design/module-system.md) | draft |
| [`design/persistence-and-orm.md`](./design/persistence-and-orm.md) | draft |
| [`design/scaffolding-and-upgrade.md`](./design/scaffolding-and-upgrade.md) | draft |
| [`features/README.md`](./features/README.md) (catalogue) | draft |

Once a doc moves to `accepted`, that is the contract; further changes require either
an `enh-NNN` (additive) or a new design doc that supersedes it.
