# enh-001: MCP server-side HTTP transport

> Improves a *shipped* feature (feat-013, MCP). Reclassified from bug-016
> on 2026-06-02: the original report was filed as a defect, but the HTTP
> server transport is an explicit, documented `not yet implemented` stub
> deferred from v0.2 — a known feature gap, not a regression against
> shipped behaviour. It therefore belongs in the enhancement track.

---

## Metadata

| Field | Value |
|---|---|
| **ID** | enh-001 |
| **Title** | Implement server-side HTTP transport for `MCPServer` |
| **Status** | `proposed` |
| **Owner** | kjoshi |
| **Created** | 2026-06-02 |
| **Target version** | 0.2.4 (or 0.2.5 if scope slips) |
| **Languages** | `python` |
| **Improves** | feat-013 (MCP) |

---

## 1. Summary

Let a Python `MCPServer` expose its tools over HTTP, not just stdio, so
MCP servers can run as multi-instance hosted services.

## 2. Motivation

The client side of HTTP MCP already works (`MCPServerClient.from_http`),
but the **server** side raises at serve time:

```
agentforge_core.production.exceptions.ModuleError:
  MCP server transport 'http' is not yet implemented. Use transport='stdio' for v0.2.
```

Verified: `_SDKServerRunner.serve()` (`agentforge_mcp/server.py:200-209`)
explicitly raises for any non-stdio transport; `MCPServer.from_http(...)`
and `register_tools()` succeed, the failure is deferred to `serve()`.

HTTP server transport is the only realistic production topology for a
multi-instance ECS-style deployment. Stdio-spawn from inside a
long-running async server also hits the upstream `mcp` SDK's anyio
cancel-scope race across lifespan boundaries (worth a separate upstream
filing), so HTTP is the path that unblocks hosted MCP servers.

## 2.5 Framework-level vs derived-agent-level

**Framework.** `MCPServer` and its transports are framework code; the
manifest defaults `expose.transport` to `stdio`. A consumer cannot
implement HTTP transport without reimplementing the framework's server
protocol layer.

- **Derived-agent test:** the workaround (hand-roll a FastAPI app + the
  `mcp` SDK protocol layer) means re-implementing the protocol envelope
  the framework is supposed to own — fails the test → framework work.
- **How it helps derived agents:** consumers expose a production MCP
  server with `MCPServer.from_http(...)` + `serve()` instead of
  re-implementing the protocol, and get a deployable multi-instance
  topology for free.

## 3. Before / after

| Aspect | Before | After |
|---|---|---|
| `from_http` server | constructs, then raises at `serve()` | serves over HTTP |
| Prod topology | stdio-spawn only (fragile across async lifespans) | multi-instance HTTP service |
| Consumer code | hand-rolled FastAPI + mcp protocol | `MCPServer.from_http(...)` |

```python
# after
server = MCPServer.from_http(tools=tools, host=host, port=port)
server.register_tools()   # or auto-registered once bug-013 lands
await server.serve()      # serves over HTTP instead of raising
```

## 4. Backward compatibility

Additive. Stdio transport is unchanged; this only makes a path that
currently raises start working. No behaviour change for existing agents.

## 5. Implementation sketch

Implement the HTTP MCP server using the upstream `mcp` SDK's HTTP / SSE
server adapter — the inverse of the client-side `_build_http_runner`.
Two phases possible:

1. HTTP-only first (the pressing transport).
2. SSE later, once the SDK's SSE server adapter stabilises.

Fail-fast improvement to fold in: `MCPServer.from_http` / the bridge's
`_server_placeholder` should reject an unsupported transport at
*construction* time rather than deferring the `ModuleError` to `serve()`.

## 6. Test plan

- Unit: `from_http` builds an HTTP runner; `serve()` no longer raises.
- Integration: spin up an HTTP `MCPServer`, connect `MCPServerClient.from_http`,
  assert `ListTools` returns the registered tools and a `CallTool` round-trips.
- Combine with bug-013's auto-register fix so HTTP servers aren't
  zero-tool.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Upstream `mcp` SDK SSE server adapter unstable | Ship HTTP-only first; defer SSE |
| anyio cancel-scope race across lifespans | HTTP transport sidesteps the stdio-spawn race; file upstream separately |

## 8. References

- Improved feature: feat-013 (MCP)
- Reclassified from: bug-016 (removed)
- Related: bug-013 (auto-register tools), bug-020 (runtime wiring)
