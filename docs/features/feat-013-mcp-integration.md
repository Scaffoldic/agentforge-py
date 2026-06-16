# feat-013: MCP integration

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-013 |
| **Title** | Model Context Protocol — consume MCP tool servers and expose AgentForge tools as MCP |
| **Status** | shipped (Python — consume + expose, stdio + HTTP/SSE) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 (contracts + adapter + client + server + bridge — shipped); 0.2 (production HTTP/stdio runner against a real MCP server) |
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
*its* tools as MCP servers can be consumed by other agents (Claude Desktop,
Cursor, and any MCP-speaking framework) without any glue code. The agent becomes a network
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
agent = Agent(model="...", tools=["filesystem__read_file", "github__create_issue"])
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
  LLM emits tool_call(name="filesystem__read_file", arguments=...)
       │
       ▼
  Agent's tool catalogue: filesystem__read_file → MCPToolAdapter
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
| Tool name collision across servers | Prefix with server name (`filesystem__read_file`); collision detection at startup |
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
- **~~`MCPBridge.from_config` runs `asyncio.run_until_complete`~~**
  — **RESOLVED in v0.2.4 (bug-014).** This raised
  `RuntimeError: this event loop is already running` whenever
  called from an async runtime. `from_config` is now pure data
  (stashes server specs) and the async `start()` materialises the
  clients, so it is safe inside a running loop. See the v0.2.4
  table below.
- **~~`Agent.tools` integration is opt-in via the bridge~~** —
  **RESOLVED in v0.2.4 (bug-020).** `build_agent_from_config` now
  resolves `modules.protocols`, builds each handler, awaits
  `start()`, merges `bridge.tools` into the agent's tool list, and
  closes the bridges on `Agent.close()`. The documented
  `modules.protocols.mcp` config is no longer a no-op.
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

### v0.2 follow-up — production runner against a real MCP server

Shipped on the v0.1 → v0.2 line. The
`# pragma: no cover` stubs are now backed by real
implementations and gated by the framework's first
`@pytest.mark.live` integration test.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `eadcf66` | `_SDKClientRunner` real implementation: `AsyncExitStack`-managed session + transport open on first method call; `list_tools` normalises every `mcp.types.Tool` to `MCPToolDescriptor`; `call_tool` concatenates every `TextContent` block (non-text content ignored for v0.2); `close()` tears down the full stack. Root `pyproject.toml` adds `mcp>=1.0,<2` to `[dependency-groups] dev`. |
| 2 | `03bfba9` | `_SDKServerRunner` real implementation: `register_tool(...)` accumulates registrations into an in-memory registry; `serve()` applies the SDK's decorator pattern (`@server.list_tools()` returns all descriptors; `@server.call_tool()` dispatches by name into the per-tool handler), opens `mcp.server.stdio.stdio_server()`, awaits `server.run(...)`. `stop()` cancels via `contextlib.suppress`. |
| 3 | `339753e` | `agentforge-mcp` declares `[project.optional-dependencies] mcp = ["mcp>=1.0,<2"]`. `pip install agentforge-mcp[mcp]` (or transitively via `agentforge add module mcp`) brings the SDK. |
| 4 | `175fdfa` | Live integration test: `tests/integration/_echo_server.py` exposes one tool; `tests/integration/test_mcp_live.py` (`@pytest.mark.live`, `@pytest.mark.asyncio`) spawns the echo server as a subprocess, calls `discover_tools()` (asserts `echo.echo`), invokes the adapter's `run(text="hello mcp")`, asserts the response, closes the client. The default pre-commit / CI gate skips this via `-m "not live"`; run explicitly with `uv run pytest -m live packages/agentforge-mcp/tests/integration/`. |

### v0.2.4 — runtime wiring (bug-020 + bug-014)

The cluster of defects from the first live Bedrock-backed MCP
integration. `modules.protocols.mcp` was previously
validated-but-never-instantiated, so the documented config did
nothing.

| Chunk | What landed |
|---|---|
| 1 | **bug-014** — `MCPBridge.from_config` is now pure data (no event loop driven); the async `start()` materialises deferred client specs and discovers tools. `_await_sync` deleted. `_client_from_entry_async` awaits the transport factory directly and accepts a list-form `command:`. `MCPBridge.attach_local_tools` + `MCPServer.set_tools` implemented (closes the undefined-method loose end). |
| 2 | `agentforge_core.contracts.protocol_bridge.ProtocolBridge` — a `@runtime_checkable` Protocol (`tools` / `start` / `close`) so the runtime wires protocol handlers without `agentforge` importing `agentforge-mcp`. `Agent` gains a `protocol_bridges` kwarg and closes each on `close()`. |
| 3 | **bug-020** — `build_protocols_from_config` resolves each `modules.protocols` entry under the `protocols` category, builds it via `from_config`, awaits `start()`, and collects its tools. `build_agent_from_config` merges native `agent.tools` (previously never wired through this path) + protocol tools into `Agent(tools=...)` and passes the started bridges. Server-side `expose` is rejected with a clear error (would hijack the agent process's stdio); expose runtime-wiring is a follow-up. |
| 4 | **bug-013** — `MCPServer.from_stdio` / `from_http` now call `register_tools()` before returning, so a server built straight from the factory advertises its tools instead of serving an empty `ListTools`. `register_tools()` is idempotent (guarded), and `set_tools()` re-arms it, so the bridge expose path (build empty → `attach_local_tools` → `start()` registers) and an explicit caller both stay correct. Both factories gained an optional `runner=` injection for testing. |
| 5 | **enh-001** — `MCPServer` HTTP server transport. `_SDKServerRunner.serve()` branches on transport: `http` runs the SDK's `StreamableHTTPSessionManager` mounted at `/mcp` in a Starlette app under uvicorn (`stop()` signals graceful exit); unsupported transports are rejected at construction. The client HTTP transport was migrated off the deprecated `streamablehttp_client` to `streamable_http_client` + `create_mcp_http_client`. Live test covers an HTTP list+call round-trip. SSE server transport stays deferred. |
| 6 | **enh-003** — HTTP transport middleware seam. `MCPServer.from_http(..., middleware=[...])` threads Starlette `Middleware` into the app the default runner builds (`_build_http_app` helper, split out so the seam is unit-testable without the SDK / a live server). The seam for a bearer-token gate (or rate-limit / CORS) in front of the transport, without forking the serve path via a custom `runner`. Additive (`middleware=None` unchanged); ignored when a `runner` is supplied. Closes #93. |

### Out-of-scope (deferred to a later v0.x follow-up)

- **Server-side `expose` runtime-wiring.** Consuming MCP servers is
  wired (v0.2.4); auto-serving the agent's own tools as an MCP
  server from inside the agent runtime is not — it would hijack the
  process's stdio. `build_protocols_from_config` fails loud on
  `expose.enabled`. Tracked alongside the HTTP server transport
  (enh-001).
- **HTTP/SSE server transport for `_SDKServerRunner`.** The stdio
  path is wired; HTTP / SSE expose still raises
  `ModuleError("transport='http' not yet implemented")`. Needs
  `mcp.server.streamable_http` wiring + uvicorn integration.
  Tracked as a v0.2.1 chore.
- **Non-text content handling** (`ImageContent`,
  `EmbeddedResource`). `_SDKClientRunner.call_tool` returns only
  the concatenated text content blocks; the adapter signs the
  tool as `-> str` so binary content has no callable return
  path. Plumbed when a real use case justifies the wire format
  change.
- **`run_mcp_runner_conformance(runner)`** in
  `agentforge_core.testing.conformance`. The contract is
  exercised by injected fakes + the live test; a formal
  conformance harness lands when a second concrete runner
  (third-party) exists.
- **Dedicated "live" CI job** that runs `-m live` across every
  package shipping such tests. Lands when feat-014 A2A's matching
  production runner adds the second one; until then, live tests
  are run on developer machines on demand.

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
(`filesystem__read_file`, `github__create_issue`). The `__`
separator (not `.`) keeps the qualified name inside the
`^[a-zA-Z0-9_-]{1,64}$` charset every provider enforces (bug-012);
provider drivers also validate it at request-build time via
`validate_tool_name`, so an illegal server or tool name fails
locally with `ToolNameInvalidError` rather than as a remote error
on the first LLM call (bug-017). When `expose.enabled` is set, the
agent also runs an MCP server so Claude Desktop / Cursor / another
AgentForge agent can call into `lookup_user` and `create_ticket`
over MCP.

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
| `ModuleError: mcp SDK is not installed` | upstream missing | `pip install agentforge-mcp[mcp]` (or `agentforge add module mcp` to install both) |
| `MCP server transport 'sse' is not supported` | only `stdio` + `http` server transports ship | use `transport: stdio` or `transport: http`; SSE server transport is still deferred (enh-001 phase 2). HTTP server transport landed in v0.2.4 (enh-001). |
| Tool name collision | two servers expose the same name | both arrive prefixed with their server name (`fs__read_file` vs `s3__read_file`) — collision avoided |
| Subprocess won't terminate on agent close | `bridge.close` not called | use `async with Agent(...)` so the framework's `__aexit__` invokes the bridge close path |
| Non-text content blocks dropped from `call_tool` result | `_SDKClientRunner` concatenates `TextContent` blocks and ignores `ImageContent` / `EmbeddedResource` for v0.2 | follow-up when a real use case justifies the wire-format change; meanwhile route binary tools through a different adapter shape |

## 12. References

- [`architecture.md`](../design/architecture.md) §5
- feat-001, feat-004, feat-010
- MCP spec: https://modelcontextprotocol.io
- Anthropic MCP servers: https://github.com/modelcontextprotocol/servers
