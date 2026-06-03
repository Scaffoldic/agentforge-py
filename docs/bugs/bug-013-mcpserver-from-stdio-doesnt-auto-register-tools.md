---
status: fixed in 0.2.4
severity: P2
found-in: v0.2.3
found-via: live integration of a Bedrock-backed MCP agent (Khemchand Joshi, 2026-05-27)
---

> **Severity revised P0 → P2 after source verification (2026-06-02).** The
> orchestrated path is *not* affected: `MCPBridge.start()` already calls
> `self._server.register_tools()` before serving (`bridge.py:77-79`). The
> gap is only on the *raw factory* surface — a consumer who calls
> `MCPServer.from_stdio(...)` directly (as the reporter did, building a
> standalone MCP server) must call `register_tools()` themselves. This is
> an API-ergonomics / docstring defect, not a broken behaviour.

# bug-013 — `MCPServer.from_stdio` / `from_http` don't auto-call `register_tools` → `ListTools` returns empty

## Symptom

Server side: `MCPServer.from_stdio(tools=[...])` constructs the server
holding the tool list internally (`self._tools`), but the underlying
MCP runner is never told about them. Subsequent `ListToolsRequest`
from any connected client returns an empty list.

Symptom from the consumer's view (e.g. a downstream consumer MCP bridge):

```
[DEBUG mcp] bridge_tools=[] per_client={'<server>': []}
```

Even though our `mcp_server/server.py` constructs the server with 7
tools (and logs `mcp_server_serve`).

## Reproduction

```python
from agentforge_mcp import MCPServer
from my_tools import build_all_tools  # returns a list of 7 Tool subclasses

server = MCPServer.from_stdio(tools=build_all_tools(), server_name="my-mcp")
await server.serve()
# Connect a client; ListToolsRequest returns [].
```

## Root cause

`agentforge_mcp/server.py`:

- `from_stdio(...)` → `cls(tools=tools, runner=runner, allowed=allowed)`
  → `__init__` does `self._tools = list(tools)`. **`runner.register_tool(...)` is never called.**
- `register_tools()` is a separate public method on `MCPServer` that
  walks `self._tools` and registers each via the runner. The consumer
  must call it explicitly before `serve()`.

This is undocumented in `from_stdio`'s docstring; the example pattern in
tests and template `server.py` files spells out
`server = MCPServer.from_stdio(tools=...); await server.serve()`,
which silently produces a zero-tool server. (Note: there is no "runbook
09" in the docs tree — docs are organised as `feat-NNN` specs; the
reporter's reference to runbooks is from an assumed doc layout that does
not exist here.)

## Fix proposal

Call `self.register_tools()` from the end of `from_stdio` / `from_http`
classmethods, before returning the instance. `register_tools()` is
already documented as allowlist-aware (skips disallowed names), so the
call is safe to fold into construction.

Or: rename the public method to `register_pending()` and call it from
the constructor, leaving the explicit form for advanced use only.

## Workaround

After `MCPServer.from_stdio(...)`, call `server.register_tools()`
manually before `await server.serve()`. the MCP server does this
explicitly with a comment pointing at this bug.

## Framework-level vs derived-agent-level

**Framework (low severity).** The two-step factory contract is framework
API shape, so the consumer can't make the public surface less
foot-gunny without forking it. But the impact is bounded: anyone driving
MCP through `MCPBridge` (the supported path) is unaffected because
`start()` already registers tools.

- **Derived-agent test:** the *workaround* (call `register_tools()`
  yourself) is a one-liner in consumer code and doesn't touch framework
  internals — which is why this is P2, not P0. The framework-level fix is
  about removing the foot-gun, not unblocking a broken path.
- **How the fix helps derived agents:** folding `register_tools()` into
  `from_stdio`/`from_http` deletes a silent zero-tool-server failure mode
  for every consumer who builds a standalone MCP server from the factory,
  and aligns the raw-factory path with the bridge path's behaviour.

## Resolution (v0.2.4)

`from_stdio` and `from_http` now call `register_tools()` before returning,
so a server built from the factory advertises its tools without a manual
step. Two correctness guards make the auto-call safe:

- **Idempotency** — `register_tools()` is guarded by a `_registered`
  flag; a second call (e.g. an existing caller that still invokes it
  explicitly) registers nothing and returns 0, so no double-registration.
- **`set_tools()` re-arms** the flag, so the bridge expose path (build an
  empty placeholder → `attach_local_tools` → `start()` registers the real
  tools) still works; the empty placeholder's auto-registration is a
  harmless no-op.

Both factories also gained an optional `runner=` injection (matching the
client factories) so the behaviour is unit-tested with a fake runner
rather than only in the live path. The `register_tools()` return value is
now "tools registered by this call" (0 on a no-op repeat).
