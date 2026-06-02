---
status: open
severity: P1
found-in: v0.2.3
found-via: live integration of a Bedrock-backed MCP agent (Khemchand Joshi, 2026-05-27)
---

# bug-014 — `MCPBridge.from_config` uses `asyncio.run` internally → fails inside a running event loop

## Symptom

Calling `MCPBridge.from_config(...)` from inside an existing event
loop (e.g. FastAPI's `lifespan`, an `asynccontextmanager`, or any
async startup hook) raises:

```
RuntimeError: this event loop is already running.
```

Stack trace bottoms out at:

```
File ".../agentforge_mcp/bridge.py", line 147, in _await_sync
    raise RuntimeError('this event loop is already running.')
```

## Root cause

`MCPBridge.from_config` is a synchronous classmethod (`bridge.py:47`)
that builds each `MCPServerClient` by calling the async
`from_stdio` / `from_http` / `from_sse` classmethod and awaiting the
result via `_await_sync`. **Verified:** `_await_sync` (`bridge.py:145`)
is `asyncio.get_event_loop().run_until_complete(coro)` — not
`asyncio.run` as the stack-trace excerpt above suggested, but it fails
identically: `run_until_complete` raises `RuntimeError: this event loop
is already running` whenever a loop is active on the thread. The whole
sync path is `# pragma: no cover`, so it ships untested. (The bridge's
own comment at `bridge.py:50-55` claims construction is "async-friendly"
because the client factories "return synchronously" — they don't; they
are `async def`.)

The natural place to call `MCPBridge.from_config(...)` is during app
startup. For any async runtime (FastAPI, Starlette, Litestar, AnyIO
task groups, etc.), the startup hook itself runs inside the event loop —
so `from_config` is unusable from the documented integration site.

## Fix proposal

Convert `MCPBridge.from_config` to an async classmethod:

```python
@classmethod
async def from_config(cls, config: dict[str, Any]) -> MCPBridge:
    clients = []
    for entry in config.get("servers", []) or []:
        clients.append(await _client_from_entry_async(entry))
    server = _build_server_from_config(config) if config.get("expose") else None
    return cls(clients=clients, server=server)
```

Or: keep `from_config` synchronous, but provide an
`MCPBridge.from_config_async(...)` companion that's safe to call from
inside a running loop. Less ergonomic but backwards-compatible.

## Workaround

Consumers build clients themselves via `await MCPServerClient.from_stdio(...)`
inside their async startup hook, then pass them to `MCPBridge(clients=[...])`
(the constructor is plain). a downstream consumer does this in
`agent_factory.startup()`.

## Framework-level vs derived-agent-level

**Framework.** `from_config` is the framework's config-driven
construction entry point, intended to be called from the (async) agent
runtime once bug-020 wires it in. Driving a bridge from config while a
loop is running will reliably raise.

- **Derived-agent test:** the consumer's workaround (build clients
  manually, pass to the plain `MCPBridge(clients=[...])` constructor)
  works but bypasses the documented `from_config` entry point — i.e. it
  only works *because* they're re-implementing the framework's job. Once
  bug-020 lands, the framework itself would hit this, so it cannot be
  pushed to consumers. Framework defect.
- **How the fix helps derived agents:** an async `from_config` (or an
  `await`-able lifecycle inside `start()`) lets every consumer wire MCP
  by config from inside their existing async startup hook (FastAPI
  `lifespan`, etc.) with no hand-rolled client construction.

## Notes

- **Couples with bug-020** (runtime doesn't wire `modules.protocols.mcp`).
  Once bug-020 is fixed, the framework's own wiring is the first victim of
  this bug — so 014 must be fixed *as part of* the 020 wiring, with bridge
  construction async end-to-end. (Earlier drafts called the wiring bug
  "bug-011" before it was renumbered to bug-020.)
- Also affects `_client_from_entry` which does `str(entry["command"])`
  on a list-typed YAML command — minor cosmetic, folding into the same
  fix.
