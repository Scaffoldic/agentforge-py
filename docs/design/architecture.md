# Architecture: AgentForge

## Metadata

| Field | Value |
|---|---|
| **Title** | AgentForge — system architecture |
| **Status** | draft |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Last updated** | 2026-05-09 |
| **Applies to version** | 0.x (pre-alpha) |

---

## 1. Purpose

AgentForge is a plug-and-play framework for building production AI agents in Python
and TypeScript. This doc is the canonical reference for how the system fits together
— what is locked, what is open, what is shipped where.

It does **not** propose changes; design docs do that. When a design doc is accepted
and the change lands in code, the relevant section here is updated.

## 2. Context within AgentForge

```
                ┌──────────────────────────────────────────────┐
                │              your agent code                 │
                │   (tools, prompts, pipeline tasks, config)   │
                └──────────────────────┬───────────────────────┘
                                       │ uses
                                       ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │                       agentforge (runtime)                         │
   │       Agent · ReAct loop · default tools · default findings        │
   └─────────┬────────────────────────────────────────────┬─────────────┘
             │ implements                                 │ orchestrates
             ▼                                            ▼
   ┌────────────────────────┐               ┌────────────────────────────┐
   │    agentforge-core     │               │   opt-in modules           │
   │       (contracts)      │◄──implements──┤   agentforge-anthropic     │
   │                        │               │   agentforge-memory-*      │
   │   Agent ABC            │               │   agentforge-mcp           │
   │   ReasoningStrategy    │               │   agentforge-otel          │
   │   LLMClient            │               │   agentforge-eval-*        │
   │   Tool                 │               │   ...                      │
   │   MemoryStore          │               └────────────────────────────┘
   │   Evaluator                                          ▲
   │   Finding (Protocol)                                 │ register via
   │   Budget · run_id                                    │ entry points
   └────────────────────────┘                             │
                                                          │
                                       ┌──────────────────┴────────────────┐
                                       │  agentforge.yaml (your config)    │
                                       │  picks which modules are active   │
                                       └────────────────────────────────────┘
```

## 3. Key concepts

| Concept | Definition |
|---|---|
| **Agent** | The top-level orchestrator. Owns config, picks a strategy, runs the loop, returns a result. The thing developers instantiate. |
| **ReasoningStrategy** | The shape of the agent loop — ReAct, Plan-Execute, Tree-of-Thoughts, Multi-Agent. Pluggable. |
| **Tool** | A typed callable the agent can invoke. Defined with `@tool` decorator or `Tool` ABC. |
| **MemoryStore** | The unified persistence layer. Single ABC, multiple drivers (sqlite/postgres/surrealdb/neo4j). |
| **Evaluator** | *Post-run* quality scorer. Built-in deterministic graders + LLM-judge for correctness / faithfulness / groundedness / hallucination / relevance / helpfulness. |
| **Validator / Gate** | *Real-time* safety primitive. `InputValidator` (before LLM), `OutputValidator` (after LLM), `ToolCallGate` (before tool dispatch). Distinct from Evaluator: validators block/redact, evaluators score. |
| **Finding** | The shape of an output item. Protocol with shipped variants (Simple, Patch, Narrative, MultiSpan). |
| **Budget** | A per-run cost cap (USD + tokens) checked before every LLM call. |
| **run_id** | A correlation id propagated through every log line, span, tool call, and module. Anchors structured logging and distributed tracing. |
| **Module** | An opt-in pip-installable package that plugs into one of the contracts above. Self-registers via entry points. |
| **ProviderRegistry** | Per-agent map from role-name → instantiated client. A real agent runs multiple LLMs (reasoning + judge) and at least one embedding client; the registry lets every component reference them by role-name in YAML rather than hard-coding provider/model strings. |
| **ChatSession** | A stateful wrapper over `Agent` for conversational deployments. Owns conversation history (via `ChatHistoryStore`), per-turn `run_id`, per-turn budget, streaming. One `Agent` is one-shot; one `ChatSession` is a multi-turn conversation backed by that `Agent`. |
| **ChatHistoryStore** | Persistent store of chat turns, parallel to `MemoryStore` (claims) but a different concern. Multiple drivers (memory/sqlite/postgres/redis), session-id-scoped, TTL-aware. |

## 4. The contract

The contract lives in `agentforge-core` and is what every module implements. These
ABCs are **locked** — changing them requires a design doc and a major version bump.

### 4.1 Python

```python
# agentforge-core / agentforge_core/contracts.py
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Protocol, runtime_checkable

class LLMClient(ABC):
    @abstractmethod
    async def call(self, system: str, messages: list[dict], tools: list[dict] | None = None) -> dict: ...
    @abstractmethod
    async def close(self) -> None: ...
    def capabilities(self) -> set[str]: return set()

class EmbeddingClient(ABC):
    @abstractmethod
    async def embed(self, texts: list[str], *, kind: str = "document") -> EmbeddingResponse: ...
    @abstractmethod
    async def close(self) -> None: ...
    @property
    @abstractmethod
    def dimensions(self) -> int: ...

class Tool(ABC):
    name: str
    description: str
    @abstractmethod
    async def run(self, **kwargs: Any) -> Any: ...

class ReasoningStrategy(ABC):
    @abstractmethod
    async def run(self, state: "AgentState") -> "AgentState": ...

class MemoryStore(ABC):
    @abstractmethod
    async def put(self, claim: "Claim") -> str: ...
    @abstractmethod
    async def get(self, claim_id: str) -> "Claim | None": ...
    @abstractmethod
    async def query(self, **filters: Any) -> list["Claim"]: ...

class Evaluator(ABC):
    name: str
    @abstractmethod
    async def evaluate(self, finding: "Finding", context: dict) -> "EvalResult": ...

@runtime_checkable
class Finding(Protocol):
    severity: str
    category: str
    message: str
    def to_dict(self) -> dict[str, Any]: ...
```

### 4.2 TypeScript

```typescript
// @agentforge/core
export interface LLMClient {
  call(system: string, messages: Message[], tools?: ToolSpec[]): Promise<LLMResponse>;
  close(): Promise<void>;
  capabilities(): Set<string>;
}

export interface Tool {
  name: string;
  description: string;
  run(args: Record<string, unknown>): Promise<unknown>;
}

export interface ReasoningStrategy {
  run(state: AgentState): Promise<AgentState>;
}

export interface MemoryStore {
  put(claim: Claim): Promise<string>;
  get(claimId: string): Promise<Claim | null>;
  query(filters: Record<string, unknown>): Promise<Claim[]>;
}

export interface Evaluator {
  name: string;
  evaluate(finding: Finding, context: Record<string, unknown>): Promise<EvalResult>;
}

export interface Finding {
  severity: 'critical' | 'warning' | 'suggestion' | 'info';
  category: string;
  message: string;
  toDict(): Record<string, unknown>;
}
```

Both languages declare the same contract. Idiomatic differences (ABC vs interface,
async/await vs Promise) are allowed; semantics must match.

## 5. Reference implementations

`agentforge-core` ships only contracts, types, and a tiny in-memory `MemoryStore`
fallback for tests. No I/O, no third-party SDKs.

`agentforge` (the runtime/prebuilts package) ships the defaults a developer expects
on a fresh install:

- `Agent` orchestrator
- `ReActLoop` — the stable default reasoning strategy
- `web_search`, `calculator`, `file_read`, `shell` — minimal default tools
- `SimpleFinding` + a scorecard renderer
- 5 built-in non-LLM evaluators
- `BudgetPolicy(usd=1.0)` default
- `run_id` `ContextVar` (Py) / `AsyncLocalStorage` (TS) and stdlib log filter

Everything else is a separately installed module:

| Module package | What it implements |
|---|---|
| `agentforge-anthropic` | `LLMClient` for Anthropic SDK |
| `agentforge-bedrock` | `LLMClient` for AWS Bedrock |
| `agentforge-openai` | `LLMClient` for OpenAI |
| `agentforge-litellm` | `LLMClient` shim over LiteLLM (covers many providers in one install) |
| `agentforge-memory-sqlite` | `MemoryStore` driver for SQLite (local default) |
| `agentforge-memory-postgres` | `MemoryStore` driver for PostgreSQL |
| `agentforge-memory-surrealdb` | `MemoryStore` + `GraphStore` for SurrealDB |
| `agentforge-memory-neo4j` | `GraphStore` for Neo4j |
| `agentforge-mcp` | Adapter mapping MCP tools to AgentForge `Tool` and exposing AgentForge tools as MCP |
| `agentforge-a2a` | Agent-to-Agent protocol — call peers, expose endpoints |
| `agentforge-otel` | OpenTelemetry distributed tracing emitter |
| `agentforge-langfuse` | Langfuse observability hook |
| `agentforge-phoenix` | Phoenix (Arize) observability hook |
| `agentforge-eval-geval` | LLM-judge evaluator with rubric prompts (correctness, faithfulness, groundedness, hallucination, relevance, helpfulness) |
| `agentforge-eval-ragas` / `-deepeval` / `-toxicity` / `-codeexec` | Optional evaluator adapters |
| `agentforge-guard-llmguard` | Safety — LLM Guard scanners (jailbreak, prompt injection, secrets, etc.) |
| `agentforge-guard-presidio` | Safety — Microsoft Presidio PII detection / redaction |
| `agentforge-guard-nemo` | Safety — NeMo Guardrails programmable rails |
| `agentforge-guard-llamaguard` | Safety — Llama Guard 3 input/output classifier |
<!-- All four reasoning strategies (ReAct + Plan-Execute + ToT + Multi-Agent)
     ship in `agentforge` itself, all stable from v0.1 — no separate
     experimental package. See feat-002. -->

| `agentforge-chat` | `ChatSession` wrapper over `Agent` + `ChatHistoryStore` ABC + memory/sqlite drivers + truncation strategies |
| `agentforge-chat-history-postgres` | Postgres `ChatHistoryStore` driver |
| `agentforge-chat-history-redis` | Redis `ChatHistoryStore` driver — fast in-memory with native TTL |
| `agentforge-chat-http` | `ChatServer` — REST + WebSocket + SSE; reuses `AuthPolicy` from feat-014 |

## 6. Extension points

A developer extends AgentForge in one of three ways, in order of preference:

1. **Use a shipped module.** `pip install` + one config line. Covered by the module
   catalogue above.
2. **Write a custom implementation.** Implement the relevant ABC, register via the
   `@agentforge.register` decorator (or entry point in `pyproject.toml`). The
   developer's class is now resolvable by the same string-identifier mechanism the
   shipped modules use.
3. **Subclass and override.** Subclass a shipped class (e.g. `ReActLoop`) and pass
   the subclass to `Agent(strategy=MyReAct())`. No registration needed if you don't
   want the string-identifier path.

There is no fourth way. We deliberately do **not** support monkey-patching, runtime
class swapping, or import hooks.

## 7. Lifecycle

A run proceeds in this order, every time:

1. **Config load.** Read `agentforge.yaml`, env vars, then constructor kwargs (last
   wins). Validate via Pydantic / Zod.
2. **Module resolution.** For each `module:` entry in config, look up the registered
   class via entry point. Fail fast if missing.
3. **Agent construction.** `Agent(...)` wires strategy, LLM client, memory, tools,
   evaluators, budget, hooks, **input/output validators, tool-call gates**.
4. **`run_id` set.** Generate a UUID; bind to context-local; attach log filter.
5. **Input validation** (feat-018). User task passed through `InputValidator`s.
   Block / redact / warn per `GuardrailPolicy`.
6. **Strategy.run().** The loop executes until `finish` / iteration cap / cost
   guardrail (feat-007) / safety guardrail (feat-018) trip. Every iteration:
   cost-guardrail check → LLM call → output validation → tool-call gate →
   tool dispatch → state update.
7. **Evaluation.** If evaluators are configured, score the produced findings
   (cost-bounded by remaining budget).
8. **Hooks.** `on_step` fires per iteration; `on_finish` fires once at the end.
9. **Teardown.** Close the LLM client; flush hooks; persist any pending claims;
   close memory store and any module-owned resources (MCP subprocesses, OTel
   exporter, etc.).

## 7a. Developer experience layer

Every scaffolded project ships, in addition to its code:

- `docs/runbooks/` — 16 task-oriented guides (one per common operation:
  add tool, add memory, switch reasoning strategy, etc.) authored at
  the framework level and rendered into the project at scaffold time.
- `AGENTS.md` — the canonical AI-assistant rules file. Tool-agnostic
  format; read by Claude Code, Cursor, and other AI tools.
- `CLAUDE.md` and `.cursorrules` — thin pointers to `AGENTS.md` so
  each tool's native discovery still works.
- `agentforge docs` CLI — opens runbooks, reports drift vs framework.

Runbooks and `AGENTS.md` are *managed files* (per the scaffolding/upgrade
design) — they update with the framework via Copier merge. Custom
content goes in fenced sections that survive upgrades. See feat-019.

## 7b. Deployment shapes

`Agent` is one-shot by design (one `run()` → one `RunResult`). For
deployments that don't fit that mould, the framework provides
*deployment-shape modules* that wrap `Agent` while preserving every
core primitive (tools, multi-provider, guardrails, observability,
budget):

- **CLI / batch** — the default. `agentforge run "..."`.
- **Chat / conversational** — `ChatSession` from feat-020. Wraps an
  `Agent`, owns conversation history, streams chunks, exposes via
  HTTP/WebSocket/SSE through `ChatServer`. Multi-tenant by session-id.
- **Cross-agent (A2A)** — feat-014. Wraps an `Agent` as an HTTP
  endpoint that other frameworks and clients (e.g. Claude Desktop)
  can call.
- **Future** — voice, IDE plugin, etc. Each is a wrapper module; none
  changes the `Agent` contract.

## 8. Failure modes

| Mode | Surface | Recovery |
|---|---|---|
| LLM provider 5xx | `ProviderError` raised; fallback chain (if configured) tries next provider | Configure `FallbackChain` |
| Budget exceeded | `BudgetExceeded` raised before the call that would breach | Increase budget, or accept partial result |
| Guardrail trip (token cap, error streak) | `GuardrailViolation` raised with diagnostic | Adjust config; check tool errors |
| Tool exception | Captured and surfaced to the LLM as an observation; counted toward error streak | Fix the tool; the agent learns from the observation |
| Module missing at config-resolution time | `ModuleNotRegisteredError` at startup, listing the expected entry point | `pip install agentforge-<module>` |

## 9. Cost & performance characteristics

- One LLM call per ReAct iteration; iterations capped (default 25, configurable).
- Plan-Execute: 1 plan call + N step calls (parallel) + 1 synthesis call ≈ N+2.
- Tree-of-Thoughts: branch_factor × depth + scoring calls; pre-reserves budget.
- Multi-Agent: supervisor + (workers × per-worker budget). Workers inherit
  *remaining* supervisor budget — never multiplicative.
- Memory writes: O(1) per claim for SQLite/Postgres; O(1) put + O(graph_depth) for
  graph queries on SurrealDB/Neo4j.
- Cold start (no module imports beyond core): &lt; 50ms target on Python 3.13.

Real numbers go in feature docs once benchmarked.

## 10. Cross-language parity

**Identical across Python and TypeScript:**

- The contracts (Section 4)
- The default reasoning strategy (ReAct)
- The default findings + renderers
- `agentforge.yaml` schema
- The CLI commands (`agentforge new`, `agentforge add`, `agentforge upgrade`,
  `agentforge run`)
- The module-naming convention

**Allowed to differ:**

- Async primitives: `async/await` in both, but Python uses `asyncio` / `ContextVar`
  while TS uses native promises / `AsyncLocalStorage`.
- Type system idioms: ABC + `runtime_checkable Protocol` in Python; `interface` in
  TS.
- Build tooling: `uv` workspaces in Python; `pnpm` workspaces in TS.
- SDK clients: each language uses the canonical SDK for the provider.

**Deferred or staged in one language:**

Tracked per feature in feature docs (`Languages` field). Default expectation is
both, with Python landing first during 0.x and TS catching up before 1.0.

## 11. Where to learn more

- [`design-principles.md`](./design-principles.md) — the rules every feature follows
- [`module-system.md`](./module-system.md) — how modules register and load
- [`persistence-and-orm.md`](./persistence-and-orm.md) — the memory store layer in detail
- [`scaffolding-and-upgrade.md`](./scaffolding-and-upgrade.md) — `agentforge new` and `agentforge upgrade`
- [`../features/README.md`](../features/README.md) — feature catalogue
