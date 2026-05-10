# feat-013: MCP integration

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-013 |
| **Title** | Model Context Protocol — consume MCP tool servers and expose AgentForge tools as MCP |
| **Status** | proposed |
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

## 10. References

- [`architecture.md`](../design/architecture.md) §5
- feat-001, feat-004, feat-010
- MCP spec: https://modelcontextprotocol.io
- Anthropic MCP servers: https://github.com/modelcontextprotocol/servers
