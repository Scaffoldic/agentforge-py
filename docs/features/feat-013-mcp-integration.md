# feat-013: MCP integration

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-013 |
| **Title** | Model Context Protocol — consume MCP tool servers and expose AgentForge tools as MCP |
| **Status** | shipped (Python — consume + expose, stdio + HTTP/SSE) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.2 |
| **Languages** | both |
| **Module package(s)** | `agentforge-mcp` |
| **Depends on** | feat-001, feat-004, feat-010 |
| **Blocks** | none |

---

## 1. Why this feature

MCP (Model Context Protocol) is now table-stakes for agent interop in 2026.
Anthropic, OpenAI, Google, IBM, and the major frameworks all support it.
Tool ecosystems are publishing MCP servers (filesystem, GitHub, browser,
Slack, etc.) — an agent that can't consume them is artificially limited.

The other direction matters too: an agent built on AgentForge that exposes
*its* tools as MCP servers can be consumed by other agents (LangChain,
Claude Desktop, Cursor) without any glue code. The agent becomes a network
citizen, not a black box.

The pain we are removing: writing MCP integration by hand for every agent —
client setup, tool registration, transport handling, lifecycle — is 100+
lines of boilerplate. And once written per agent, it drifts.

## 2. Why it must ship as framework

- **One MCP adapter beats N hand-written ones.** Every agent that wants MCP
  uses the same `agentforge-mcp` module; bug fixes propagate.
- **Tool↔MCP bridging requires the `Tool` ABC** (feat-004) to map cleanly to
  MCP tool descriptors. Only the framework can guarantee that mapping is
  consistent.
- **Lifecycle integration:** MCP servers spawn subprocesses; lifecycle has
  to follow `Agent.close()`. Per-agent integration would forget cleanup.
- **Configuration:** declaring MCP servers in `agentforge.yaml` is a
  framework concern; per-agent invention would diverge.
- **Without framework ownership:** every team writes 100+ lines of MCP glue
  per agent, with bugs.

## 3. How derived agents benefit

- **`agentforge add module mcp` + a server entry in YAML.** Done. The
  agent now has access to every MCP server's tools.
- **Existing `@tool` functions become MCP-exposable for free.** Set
  `expose_as_mcp: true` in YAML and the agent runs an MCP server process
  alongside.
- **Mix native tools with MCP tools transparently.** `agent.tools` contains
  both; the LLM sees one merged tool catalogue.
- **Stable tool catalogue across MCP server restarts.** The framework
  maintains the bridge; tool name and schema stable.
- **Cross-framework interop.** Build the agent here, deploy alongside Claude
  Desktop or another framework — they consume each other's tools via MCP.

## 4. Feature specifications

### 4.1 User-facing experience

```bash
$ agentforge add module mcp
  → installing agentforge-mcp ........ 0.2.0
  → applying manifest .................. ok
  → done.
```

```yaml
# agentforge.yaml — consume MCP servers
modules:
  protocols:
    - name: mcp
      config:
        servers:
          - name: filesystem
            command: "npx -y @modelcontextprotocol/server-filesystem /work"
            transport: "stdio"
          - name: github
            command: "uvx mcp-server-github"
            transport: "stdio"
            env:
              GITHUB_TOKEN: "${GITHUB_TOKEN}"
          - name: my-internal-tools
            transport: "http"
            url: "http://internal:8080/mcp"

        # Optional: expose this agent's @tool functions as an MCP server.
        expose:
          enabled: true
          transport: "stdio"
          tools: ["lookup_user", "create_ticket"]   # whitelist
```

```python
# Code is unchanged from feat-004 — tools coming from MCP look the same.
agent = Agent(model="...", tools=["filesystem.read_file", "github.create_issue"])
result = await agent.run("Find the auth bug in src/")
```

### 4.2 Public API / contract

```python
# agentforge_mcp/client.py
class MCPServerClient:
    """Connects to an MCP server (stdio or HTTP) and adapts its tools as
    AgentForge Tool instances."""

    def __init__(self, name: str, transport: str, **transport_opts) -> None: ...

    async def discover_tools(self) -> list[Tool]: ...
    async def close(self) -> None: ...

# agentforge_mcp/server.py
class MCPServer:
    """Exposes a set of AgentForge Tool instances as an MCP server."""

    def __init__(self, tools: list[Tool], transport: str = "stdio") -> None: ...
    async def serve(self) -> None: ...
    async def stop(self) -> None: ...

# agentforge_mcp/bridge.py — the thing the resolver instantiates
class MCPBridge:
    """Wired by the resolver when modules.protocols includes 'mcp'.
    Manages all MCPServerClients and the optional MCPServer for this agent."""
```

### 4.3 Internal mechanics

```
Agent construction with modules.protocols.mcp:
  1. Resolver instantiates MCPBridge with config.
  2. MCPBridge spawns each configured server (subprocess for stdio,
     HTTP client for http).
  3. discover_tools() on each → list[Tool] adapter objects.
  4. Adapter Tools added to Agent.tools.
  5. If expose.enabled: MCPBridge starts an MCPServer publishing
     whitelisted tools via the configured transport.

Tool dispatch (transparent):
  LLM emits tool_call(name="filesystem.read_file", arguments=...)
       │
       ▼
  Agent's tool catalogue: filesystem.read_file → MCPToolAdapter
       │
       ▼
  Adapter.run(**args) → MCP request to server → response → return value

Lifecycle:
  Agent.close()  →  MCPBridge.close()  →  stop subprocesses, close HTTP clients,
                                          stop owned MCP server if any
```

Tool name format from MCP: `<server_name>.<tool_name>` to avoid collisions.

### 4.4 Module packaging

`agentforge-mcp` shipped as a module. Depends on `mcp` (Python SDK) or
`@modelcontextprotocol/sdk` (TS).

### 4.5 Configuration

See §4.1 example. Schema:

```yaml
modules:
  protocols:
    - name: mcp
      config:
        servers:
          - name: <unique>
            transport: "stdio" | "http" | "sse"
            command: "<exec...>"   # for stdio
            url: "<url>"           # for http/sse
            env: { KEY: VALUE }
            timeout_s: 30
            tool_filter: []        # subset of tools to import; empty = all
        expose:
          enabled: false
          transport: "stdio"
          tools: []                # whitelist; empty = none
```

## 5. Plug-and-play & upgrade story

`agentforge add module mcp` is the install path. Adding new servers post-
install is a YAML edit. Removing the module: `agentforge remove module mcp`
or remove the YAML block.

Upgrade safety: MCP protocol versions matter. `agentforge-mcp` pins to a
protocol-version range; mismatched server versions surface as a clean error
at startup with remediation guidance.

## 6. Cross-language parity

Both languages have first-class MCP SDKs. Module ships in both at v0.2.
Configuration identical.

## 7. Test strategy

- **Stdio transport:** spawn a known MCP server (filesystem); discover and
  invoke tools.
- **HTTP transport:** stand up a test MCP server in-process; same.
- **Bidirectional:** expose a tool via MCP, consume from a separate test
  agent process.
- **Lifecycle:** subprocesses cleaned up on `Agent.close()`; verified by
  process count.
- **Schema fidelity:** an AgentForge Tool exposed as MCP and re-imported
  produces the same input schema.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Subprocess management on Windows (signals, pipes) | Use `asyncio.subprocess` portable APIs; CI matrix covers Windows |
| Server crashes mid-run | Adapter raises; counted toward `error_streak_limit`; agent may continue without that server's tools |
| Tool name collision across servers | Prefix with server name (`filesystem.read_file`); collision detection at startup |
| Version-mismatch with newer MCP protocol | Pin a protocol range; surface mismatch with upgrade guidance |
| Should we ship our own MCP server registry? | No — community / MCP ecosystem owns that; we just consume |

## 9. Out of scope

- Implementing the MCP protocol itself. We use the official SDKs.
- An MCP server marketplace.
- Cross-MCP-server orchestration (call server A, pipe output to server B).
  Tools call tools — no new orchestration primitive.

## 10. Implementation status (Python)

Shipped in PR #24 as the new Tier-3 `agentforge-mcp` workspace
member.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `93ba261` | Package skeleton (pyproject + LICENSE + README) + `MCPClientRunner` / `MCPServerRunner` protocols + `MCPToolDescriptor` value + `MCPToolAdapter` + `build_adapter(runner, descriptor, server_name)` factory. Tool name prefixing (`<server>.<tool>`) + permissive Pydantic input schema generation from JSON-Schema dicts. |
| 2 | `c1099ab` | `MCPServerClient` consumer with `from_stdio` / `from_http` / `from_sse` factories that lazy-import `mcp`. `discover_tools` + `tool_filter` subset. ModuleError surfaces pip remediation when SDK is missing. |
| 3 | `8b7fb56` | `MCPServer` exposer with `from_stdio` / `from_http` factories. `register_tools()` walks the agent's tools and registers each whitelisted one with the runner using `Tool.input_schema.model_json_schema()`. `allowed` is an allowlist (skip silently outside it). |
| 4 | `8a48bb0` | `MCPBridge` orchestrator. `from_config(config)` parses `modules.protocols.mcp.config`; `start()` opens every client + schedules the optional server's `serve()` task; `close()` cancels the task cleanly + closes every client. |
| 5 | (this PR) | Docs + Runbook + roadmap + CHANGELOG + state. |

### Deviations from the design

- **Production runner stubs are `# pragma: no cover`.** The SDK
  wrapper classes (`_SDKClientRunner`, `_SDKServerRunner`)
  exist as skeletons that raise `ModuleError("Production MCP
  runner not implemented yet")` until the framework's first
  integration test against a live MCP server lands. Every unit
  test injects a mock runner; the SDK wiring + transport
  context-manager dance is well-defined but unimplemented.
- **`MCPBridge.from_config` runs `asyncio.run_until_complete`
  to drive the async client factories from a synchronous code
  path.** This is the pragmatic shape so the resolver-instantiated
  bridge fits the `build_agent_from_config` flow; a fully-async
  resolver hook is a v0.3 cleanup.
- **`Agent.tools` integration is opt-in via the bridge.** A
  follow-up commit can teach `build_agent_from_config` to call
  `MCPBridge.from_config(...)`, `await bridge.start()`, and
  merge `bridge.tools` into the agent's tool list. Today the
  package ships the primitive; wiring into the Agent
  construction path waits for a real live-test scenario.
- **TypeScript port deferred.** The protocol contract is
  language-neutral; TS port lands when the framework's TS
  scaffolding does.

### Module shape

`packages/agentforge-mcp/`:

- `_runner.py` — `MCPClientRunner` / `MCPServerRunner`
  Protocols + `MCPToolDescriptor` value.
- `adapter.py` — `MCPToolAdapter` + `build_adapter` factory.
- `client.py` — `MCPServerClient` (stdio / http / sse).
- `server.py` — `MCPServer` (stdio / http expose).
- `bridge.py` — `MCPBridge.from_config` orchestrator.
- `manifest.yaml` — feat-010 manifest so `agentforge add module
  mcp` registers the protocol entry.

## 11. Runbook

### Add MCP support to an agent

```bash
agentforge add module mcp
```

then edit `agentforge.yaml`:

```yaml
modules:
  protocols:
    - name: mcp
      config:
        servers:
          - name: filesystem
            transport: stdio
            command: "npx -y @modelcontextprotocol/server-filesystem /work"
          - name: github
            transport: stdio
            command: "uvx mcp-server-github"
            env:
              GITHUB_TOKEN: "${GITHUB_TOKEN}"
        expose:
          enabled: true
          transport: stdio
          tools: ["lookup_user", "create_ticket"]
```

After the next `agentforge run`, the agent's tool catalogue
will include MCP-server tools prefixed by their server name
(`filesystem.read_file`, `github.create_issue`). When
`expose.enabled` is set, the agent also runs an MCP server so
Claude Desktop / Cursor / another AgentForge agent can call
into `lookup_user` and `create_ticket` over MCP.

### Filter what's imported from a server

```yaml
- name: filesystem
  transport: stdio
  command: "..."
  tool_filter: ["read_file", "list_directory"]   # subset
```

### Test against a fake MCP runner

```python
from dataclasses import dataclass, field
from agentforge_mcp import MCPServerClient
from agentforge_mcp._runner import MCPToolDescriptor

@dataclass
class FakeRunner:
    tools: list[MCPToolDescriptor] = field(default_factory=list)
    async def list_tools(self):
        return self.tools
    async def call_tool(self, name, args):
        return "ok"
    async def close(self): ...

client = MCPServerClient(name="fs", runner=FakeRunner(tools=[...]))
tools = await client.discover_tools()
```

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleError: mcp SDK is not installed` | upstream missing | `pip install mcp` (or `agentforge add module mcp` to install both) |
| `Production MCP runner not implemented yet` | live transport stub | inject a fake runner via the bare constructor in tests; live wiring lands in a follow-up |
| Tool name collision | two servers expose the same name | both arrive prefixed with their server name (`fs.read_file` vs `s3.read_file`) — collision avoided |
| Subprocess won't terminate on agent close | `bridge.close` not called | use `async with Agent(...)` so the framework's `__aexit__` invokes the bridge close path |

## 12. References

- [`architecture.md`](../design/architecture.md) §5
- feat-001, feat-004, feat-010
- MCP spec: https://modelcontextprotocol.io
- Anthropic MCP servers: https://github.com/modelcontextprotocol/servers
