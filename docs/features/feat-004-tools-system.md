# feat-004: Tools system

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-004 |
| **Title** | Tools system — `@tool` decorator, `Tool` ABC, default tool set |
| **Status** | proposed |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 |
| **Languages** | both |
| **Module package(s)** | `agentforge` (default tools), tools may live in any module |
| **Depends on** | feat-001 |
| **Blocks** | feat-013 (MCP) |

---

## 1. Why this feature

Tools are how an agent does anything in the world. Every framework has them;
every framework spells them differently. LangChain wants subclasses with verbose
schemas; OpenAI's raw API wants JSON schemas you write by hand; some frameworks
make you implement `args_schema` separately from the function. The boilerplate
tax per tool ranges from 10 to 50 lines.

Worse, the JSON-schema-by-hand style decouples the tool's input contract from
the function signature, so the type checker can't help, the schema drifts from
the implementation, and runtime errors surface as confusing LLM tool-call
failures instead of clean stack traces.

The pain is universal: writing five tools should take five minutes, not five
hours. And switching from "I'll use Python's `requests` here" to "actually I
want this exposed via MCP to other agents" should not require rewriting the
tool.

## 2. Why it must ship as framework

- **Schema inference is a one-time engineering cost.** Decorator parses signature
  + docstring → JSON schema once, every tool author benefits forever. If each
  agent does its own decorator, they all reimplement the same thing slightly
  differently.
- **Tool dispatch is the security perimeter.** Argument validation, capability
  checks, and audit logging happen at the `Tool.run()` boundary. If tools are
  ad-hoc functions, that perimeter is invisible.
- **MCP interop (feat-013) requires a stable Tool shape.** Bridging in/out of
  MCP only works if AgentForge tools and MCP tools speak the same vocabulary at
  the framework layer.
- **Cross-cutting concerns** — cost attribution per tool, rate limiting per tool,
  tool-call replay during testing — only work if every tool goes through one
  contract.
- **Without framework ownership:** schemas drift, tool definitions are
  copy-pasted between agents, MCP integration is reinvented per agent, and
  cross-agent tool-calling is impossible.

## 3. How derived agents benefit

- **Five-line tool definition.** Decorate a typed function; done.
- **Free schema, free validation.** Pydantic input model inferred from type
  hints; bad LLM tool calls rejected before reaching code.
- **MCP for free.** Once MCP is installed (feat-013), every `@tool`-decorated
  function is automatically exposable as an MCP server endpoint, and every MCP
  tool is automatically usable as if local.
- **Stateful tools when needed.** Subclass `Tool` for tools that hold a DB
  connection or auth state; same dispatch path.
- **Sharable tool packages.** `agentforge-tools-github`, `agentforge-tools-aws`
  ship as third-party packages; agents `pip install` and add to the tool list.
- **Test isolation.** Replace any tool with a fake during tests
  (`FakeTool.fake("web_search", lambda q: "stub")`); production code runs
  unchanged.

## 4. Feature specifications

### 4.1 User-facing experience

```python
from agentforge import tool

# Decorator on a typed function — schema inferred from signature + docstring.
@tool
def lookup_user(user_id: str, include_email: bool = False) -> dict:
    """Fetch a user record.

    Args:
        user_id: The internal user id (ULID).
        include_email: When True, include the email field in the response.

    Returns:
        A dict with name, signup_date, and optionally email.
    """
    return db.get_user(user_id, with_email=include_email)


# Subclass for stateful tools.
from agentforge import Tool
class GitHubClient(Tool):
    name = "github_client"
    description = "Read and comment on GitHub PRs."

    def __init__(self, token: str):
        self._client = GitHub(token=token)

    async def run(self, action: str, **kwargs) -> dict:
        return await getattr(self._client, action)(**kwargs)


# Default tools shipped with `agentforge`.
from agentforge.tools import web_search, calculator, file_read, shell

agent = Agent(
    model="anthropic:claude-sonnet-4.7",
    tools=[web_search, calculator, lookup_user, GitHubClient(token="...")],
)
```

```typescript
import { tool, Agent } from 'agentforge';
import { z } from 'zod';

const lookupUser = tool({
  name: 'lookup_user',
  description: 'Fetch a user record',
  schema: z.object({
    userId: z.string(),
    includeEmail: z.boolean().default(false),
  }),
  async run({ userId, includeEmail }) {
    return await db.getUser(userId, includeEmail);
  },
});

const agent = new Agent({ model: 'anthropic:claude-sonnet-4.7', tools: [lookupUser] });
```

### 4.2 Public API / contract

```python
# agentforge_core/contracts/tool.py — locked
class Tool(ABC):
    name: str
    description: str
    input_schema: type[BaseModel]   # Pydantic model
    capabilities: set[str] = set()  # "filesystem", "network", "shell", "destructive"

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any: ...

    def to_spec(self) -> ToolSpec:
        """Provider-agnostic JSON schema description for the LLM."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            schema=self.input_schema.model_json_schema(),
        )

# agentforge/tool_decorator.py
def tool(fn: Callable | None = None, *, name: str | None = None) -> Tool:
    """Wrap a typed function as a Tool. Schema inferred from signature + docstring."""
```

The decorator builds a `Tool` subclass on the fly:
- `name` defaults to the function's name
- `description` parses from the docstring (Google or NumPy style)
- `input_schema` built from type hints; required vs optional inferred from
  defaults
- `run()` dispatches to the wrapped function, validating kwargs against
  `input_schema` first

### 4.3 Internal mechanics

Tool dispatch inside a strategy:

```
LLM emits tool_call(name="lookup_user", arguments={"user_id": "01HX..."})
            │
            ▼
   resolve `name` in agent's tool catalogue (dict by name)
            │
            ▼
   Tool.input_schema.model_validate(arguments)
            │           │
            │           └── on ValidationError: surface to LLM as observation
            ▼
   Tool.run(**validated_args)
            │
            ▼
   capture (success | exception | timeout)
            │
            ▼
   Step(kind="observe", tool_call=..., content=result, cost_usd=0)
            │
            ▼
   appended to state.steps; on_step fires
```

Tool errors are NOT raised to the strategy — they are appended as observations
so the LLM can see them and recover. Repeated errors trip the
`error_streak_limit` guardrail (feat-007).

### 4.4 Module packaging

- `agentforge` ships the `@tool` decorator, `Tool` ABC, and four default tools
  (`web_search`, `calculator`, `file_read`, `shell`).
- Third-party tools ship as separate packages and register via entry point
  `agentforge.tools.<name>`.
- Per-agent tools live in the agent's own code; no registration needed if
  passed directly to `Agent(tools=[...])`.

### 4.5 Configuration

```yaml
agent:
  tools:
    - "web_search"        # name lookup via entry point
    - "calculator"
    - "github_client":     # configured tool
        token: "${GITHUB_TOKEN}"
        repo: "myorg/myrepo"

  tool_options:
    timeout_s: 30
    max_concurrent: 4
    on_error: "observe"   # "observe" (default) | "raise"
```

## 5. Plug-and-play & upgrade story

A new tool package: `pip install agentforge-tools-aws`, then add `aws_s3_get`,
`aws_lambda_invoke`, etc. to the tool list. Tool authors version their packages
independently of the framework; tool API is anchored on the `Tool` ABC, which
is locked.

Upgrading: tool packages bump independently. The shape of `Tool` changes only
on framework majors.

## 6. Cross-language parity

Decorator + ABC pattern in both languages. Schema source of truth: Pydantic in
Python, Zod in TS. Schema-shape contract in `to_spec()` is identical (JSON
schema dict).

## 7. Test strategy

- **Decorator unit tests:** every supported type hint shape resolves to the
  expected JSON schema fragment.
- **Conformance for `Tool`:** input validation, error surfacing, timeout
  honouring, capability declaration honesty.
- **Default tool integration:** `web_search` against a stub server, `shell`
  against an isolated subprocess, `file_read` against a temp dir.
- **Replay:** record real tool calls during one test run, replay during
  subsequent runs without hitting the network.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Decorator misparses unusual type hints (TypedDict, generics, unions of unions) | Conformance test covers the common shapes; unsupported shapes raise at decoration time, not at runtime |
| `shell` tool default = security risk | Disabled by default in production tier; opt-in only for development; sandboxed subprocess; capability `"destructive"` declared |
| `file_read` traversal vulnerabilities | Default tool restricts to `cwd`; explicit `allowed_paths` config required |
| Should we ship a `python_repl` / `code_interpreter` tool by default? | No — too dangerous as default; ship as `agentforge-tools-code-interpreter` with E2B/Docker sandbox required |
| Tool name collisions across packages | Resolver fails at startup if two registered tools share a name; user picks via `providers.tools.preferred` |
| Should `@tool` support sync functions? | Yes — wrap in `asyncio.to_thread` automatically; document the perf cost |

## 9. Out of scope

- A "tool marketplace" UI. Discovery is via PyPI/npm naming convention and the
  module catalogue.
- Cross-tool transactions (rollback if one tool fails after another succeeded).
  Idempotency is the answer (feat-007), not transactions.
- Tool composition / chaining DSL. Tools call other tools via plain function
  calls; the framework doesn't add a layer.

## 10. References

- [`architecture.md`](../design/architecture.md) §4
- [`design-principles.md`](../design/design-principles.md) — P1, P7
- feat-001 (`Agent.tools=` consumes these)
- feat-013 (MCP — bridges Tool ↔ MCP both directions)
- feat-016 (testing — mocks tools)
- Prior art: Pydantic AI's `@agent.tool`, smolagents' `@tool`, Strands' `@tool`

---

## Implementation status

**Status: shipped (Python). TypeScript port pending.**

Landed via PR #10 on `feat/004-tools-system` (six chunks).

| Chunk | Commit | Scope |
|---|---|---|
| 1 | `6ec7c13` | `@tool` decorator (signature + Google docstring → Pydantic schema → `Tool` subclass; bare and parameterised forms; sync + async dispatch; decoration-time validation) |
| 2 | `97e2acc` | `calculator` (AST-based, no `eval`) and `file_read` / `FileReadTool` (sandboxed reads, size cap) |
| 3 | `c5be0f5` | `shell` / `ShellTool` (subprocess via `create_subprocess_exec`, `shell=False`, timeout, output cap, optional whitelist) and `web_search` / `WebSearchTool` (pluggable backend with DuckDuckGo HTML default + warning fallback) |
| 4 | `20c9dc6` | `_StrategyBase._dispatch_tool` — centralised tool-call dispatch (validation → observation, timeout, exception → observation). `ReActLoop` and `PlanExecuteLoop` refactored to use it. |
| 5 | `4ac290a` | `agentforge._testing.FakeTool.fake(name, response_or_fn)` — minimal scripted-response Tool for unit tests |
| 6 | (this commit) | CHANGELOG, Implementation status, PR |

### Public surface delivered

- `from agentforge import tool` — decorator, both forms
- `from agentforge.tools import calculator, file_read, FileReadTool,
  shell, ShellTool, web_search, WebSearchTool, SearchResult`
- `from agentforge._testing import FakeTool`
- `agentforge.strategies._base.DEFAULT_TOOL_TIMEOUT_S = 30.0` — the
  default per-tool execution timeout

### Capability vocabulary in use

`{"filesystem", "network", "shell", "destructive"}` declared per
default tool:
- `calculator` → `frozenset()` (pure computation)
- `file_read` → `{"filesystem"}`
- `web_search` → `{"network"}`
- `shell` → `{"shell", "destructive"}`

Future safety guardrails (feat-018) consume this vocabulary to
gate destructive tool use.

### Deviations from this spec

- **Decorator location**: spec §4.2 placed it at
  `agentforge.tool_decorator`. Shipped at
  `agentforge._tools.decorator` and re-exported as
  `from agentforge import tool` — same public surface; cleaner
  internal namespace alongside the four default tools.
- **Docstring format**: spec said "Google or NumPy". Shipped with
  Google-style only. NumPy support can land later if asked; the
  framework's own default tools all use Google so the parser is
  exercised in production.
- **`web_search` default backend**: spec didn't lock a backend.
  Shipped with a pluggable `search_fn=` plus a DuckDuckGo HTML
  scrape default that emits a warning log when the page format
  drifts. Real backends (Serper, Tavily, Brave) ship as separate
  module packages later.
- **`shell` default whitelist**: spec didn't specify. Shipped with
  `allowed_commands=None` (any binary), but heavily documented as
  destructive — operators add their own whitelist for production.
- **Config integration (`agentforge.yaml > agent.tools`)**:
  feat-012's full configuration schema lands separately. The
  default tools and `@tool`-decorated functions are usable
  programmatically today; declarative wiring follows when feat-012
  ships.

### What's *not* yet implemented

- Entry-point auto-loading of third-party tool packages — that's
  feat-010 (Module discovery).
- MCP bridging (`@tool` ↔ MCP server endpoints) — feat-013.
- Tool-level rate limiting — feat-018 (Safety).
- TypeScript port of the entire feat-004 surface.

feat-009 shipped per-tool cost attribution via the OTel hook —
`OpenTelemetryHook` emits `agent.tool_call` span events tagging
`agentforge.tool.name` + redacted args. Install `agentforge-otel`
and the costs flow to whatever OTel collector you point at.

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented "how do I…" content. This is the canonical
home for the feature's runbook; feat-011 / feat-019 consume these
sections into scaffolded agent projects.

### How do I attach tools to an agent?

```python
from agentforge import Agent
from agentforge.tools import web_search, calculator

agent = Agent(
    model="bedrock:...",
    tools=[web_search, calculator],
)
```

Pre-built tools, `@tool`-decorated functions, and `Tool`
subclasses all work interchangeably in `tools=[...]`.

### How do I write a custom tool?

Decorate a function — type hints + Google docstring drive the
schema:

```python
from agentforge import tool

@tool
async def fetch_invoice(invoice_id: str, format: str = "pdf") -> dict:
    """Look up an invoice by id.

    Args:
        invoice_id: The internal invoice identifier (e.g. INV-42).
        format: One of 'pdf' or 'json'. Defaults to 'pdf'.

    Returns:
        Dict with keys 'url' and 'amount_cents'.
    """
    return await invoice_service.get(invoice_id, format=format)

agent = Agent(model="...", tools=[fetch_invoice])
```

Sync functions are wrapped in `asyncio.to_thread` automatically.
The decorator validates at import time (fail-at-startup, P11) — a
malformed signature or unsupported type hint raises during
decoration, not during a run.

### How do I lock down `shell` for production?

`shell` declares `{"shell", "destructive"}` and is dangerous by
default. Construct it explicitly with a whitelist:

```python
from agentforge.tools import ShellTool

safe_shell = ShellTool(
    allowed_commands=["ls", "cat", "rg", "git"],
    timeout_s=10.0,
    max_output_bytes=64_000,
)
agent = Agent(model="...", tools=[safe_shell])
```

Or omit `shell` entirely. Once feat-018 (Safety) ships, the
`"destructive"` capability will gate inclusion at the framework
level; today it's the developer's responsibility.

### How do I sandbox `file_read`?

Same pattern — construct `FileReadTool` with explicit roots:

```python
from agentforge.tools import FileReadTool

reader = FileReadTool(
    allowed_paths=["/var/app/data", "/var/app/configs"],
    max_bytes=1_000_000,
)
```

Default `file_read` restricts to the process `cwd`; tighten for
anything multi-tenant.

### How do I unit-test agent logic without hitting real tools?

Use `FakeTool.fake(...)` — scripted-response Tool that bypasses
real I/O:

```python
from agentforge._testing import FakeTool

stub_search = FakeTool.fake(
    "web_search",
    response_or_fn=lambda **kw: [{"title": "Hit", "url": "https://x"}],
)

agent = Agent(model=fake_llm, tools=[stub_search])
result = await agent.run("look it up")
```

Pair with `agentforge._testing.fake_llm.echo_response(...)` for a
fully offline strategy test.

### How do I tune tool timeouts?

The strategy dispatch layer enforces a per-call timeout. Tools
that subclass `Tool` accept `timeout_s` in their constructor (see
`ShellTool` above). The framework-wide default is
`DEFAULT_TOOL_TIMEOUT_S = 30.0` — patch it for tests, override
per-tool for production:

```python
# Test setup
from agentforge.strategies import _base
_base.DEFAULT_TOOL_TIMEOUT_S = 5.0
```

A timeout raises a strategy-internal exception that becomes a
`StepKind.observe` with `metadata={"error": "...timeout..."}` so
the LLM can react and retry rather than crashing the run.

### How do I see what arguments a tool received?

Tool calls are recorded as `Step.kind == "act"` with
`step.tool_name`, `step.tool_args` (JSON-serialisable dict), and
`step.tool_result` (or error). Iterate `result.steps` after the
run, or use `on_step` to stream live:

```python
def log_tool(step):
    if step.kind == "act":
        print(f"→ {step.tool_name}({step.tool_args})")

agent = Agent(model="...", tools=[...], on_step=log_tool)
```

### When should I NOT use a default tool?

- **`web_search` in production.** The shipped default scrapes
  DuckDuckGo's HTML and is rate-limited / flaky. Switch to
  `agentforge-tools-serper` / `-tavily` / `-brave` (backlog) or
  pass your own `search_fn=` to `WebSearchTool` for production.
- **`calculator` for symbolic math.** AST-based, so it handles
  arithmetic only. For algebra / symbolic work, write a `@tool`
  around sympy.
- **`shell` without a whitelist in production.** See above —
  default `allowed_commands=None` lets the model run any binary.
