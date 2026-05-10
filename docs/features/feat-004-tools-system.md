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
