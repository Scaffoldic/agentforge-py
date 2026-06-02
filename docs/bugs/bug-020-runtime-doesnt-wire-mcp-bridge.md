---
status: open
severity: P0
found-in: v0.2.3
found-via: live integration of a Bedrock-backed MCP agent (Khemchand Joshi, 2026-05-27)
---

# bug-020 — Runtime never wires `modules.protocols.mcp` → MCPBridge → Agent.tools

## Symptom

Declaring an MCP server under `modules.protocols.mcp.config.servers`
in `agentforge.yaml` (as runbook 09 instructs) is a no-op:

- No subprocess (no `command:` from the `command:`) subprocess gets
  spawned at agent boot.
- No MCP-prefixed tools appear in the agent's tool list (the LLM
  literally says "I don't have access to mcp:myserver.my_tool").
- `agentforge health` reports `protocols:mcp resolvable` — the module
  loads — but the bridge is never instantiated or started.

## Reproduction

```yaml
# agentforge.yaml
modules:
  protocols:
    - name: mcp
      config:
        servers:
          - name: filesystem
            transport: stdio
            command: ["uv", "run", "filesystem-mcp"]
            start_timeout: 10
```

```python
async with Agent() as agent:
    print([t.name for t in agent.tools])   # → []  (or only native tools)
    # Even though runbook 09 §3 says: "Restart the agent. Discovered
    # MCP tools appear in the agent's tool list automatically; the LLM
    # sees their schemas alongside framework-native tools."
```

`ps -ef | grep filesystem-mcp` → nothing. No subprocess spawned.

## Root cause

A `grep -rn 'modules.protocols\|MCPBridge' .venv/lib/.../agentforge/`
turns up **zero** runtime call sites:

- `agentforge/agent.py` — no `MCPBridge` reference.
- `agentforge/cli/_build.py::build_agent_from_config` — wires
  memory, providers, strategy. No protocols.
- `agentforge_mcp/bridge.py::MCPBridge.from_config` — exists and is
  perfectly fine. **Nothing calls it.**
- `agentforge_mcp/manifest.yaml` — declares the config block under
  category `protocols`. The manifest is what `agentforge add module
  mcp` reads to inject the YAML; once injected, no runtime path picks
  it up.

So the integration shape is documented (runbook 09), the bridge code
is complete, the YAML schema accepts the config, but the runtime
never connects `config.modules.protocols` → `MCPBridge.from_config(...)`
→ `await bridge.start()` → `Agent(tools=[...bridge.tools()])`.

## Impact

- **Severity P0:** the entire MCP integration is non-functional out
  of the box. Every consumer that follows runbook 09 reaches this
  wall.
- **Workaround possible but invasive:** the consumer must read the
  protocols block from the parsed config in their `Agent` factory,
  construct `MCPBridge.from_config(block)`, await `bridge.start()`
  during app startup, and pass `bridge.tools()` into the
  `Agent(tools=...)` kwarg themselves.
- **Couples consumers to framework internals.** Bypassing the YAML
  contract means each downstream re-implements wiring + lifecycle.

## Fix proposal

In `agentforge/cli/_build.py::build_agent_from_config` (or in
`Agent.__init__` if we want it to also work when consumers build
Agent programmatically with `config_path=`), add a step:

```python
from agentforge_mcp import MCPBridge

protocols = config.modules.protocols or []
mcp_bridges: list[MCPBridge] = []
mcp_tools: list[Tool] = []
for entry in protocols:
    if entry.name != "mcp":
        continue
    bridge = MCPBridge.from_config(entry.config)
    await bridge.start()
    mcp_bridges.append(bridge)
    mcp_tools.extend(bridge.tools())

agent = Agent(
    ...,
    tools=[*config_native_tools, *mcp_tools],
    _mcp_bridges=mcp_bridges,   # for proper close() on Agent.aexit
)
```

And in `Agent.__aexit__` (or `close()`), close every bridge:

```python
for b in self._mcp_bridges:
    await b.close()
```

A2A (the other protocol module) likely needs the same wiring; this
fix is generic across `modules.protocols[*]` if we resolve each
entry's name to a registered protocol-handler class.

**Two coupled defects this fix must absorb:**

- **bug-014** — `MCPBridge.from_config` is sync and trips
  `RuntimeError: this event loop is already running` when driven from the
  async runtime. The wiring above calls `from_config` + `await
  bridge.start()` from an async context, so the wiring is the *first
  victim* of bug-014. Make bridge construction async end-to-end as part
  of this fix.
- **`attach_local_tools` loose end** — `bridge.py:60-62` comments
  reference an `attach_local_tools` method that **is not defined** on
  `MCPBridge`. If the expose/server path needs it, it has to be
  implemented alongside the wiring.

## Test to add

End-to-end: scaffold an agent with `modules.protocols.mcp.servers:
[{name: t, transport: stdio, command: [python, -m, mcp_echo]}]`,
where `mcp_echo` is a stub MCP server that exposes one tool.
Assert: `[t.name for t in agent.tools]` includes the prefix
`mcp:<server-name>.<tool>` after `Agent` construction completes.

## Framework-level vs derived-agent-level

**Framework — this is the root defect of the whole MCP cluster.** The
entire point of the manifest (`manifest.yaml`) and the
`agentforge.protocols` entry point is config-driven wiring;
`build_agent_from_config` already wires every other module category
(memory, providers, strategy, evaluators, retriever). Leaving
`protocols` validated-but-never-instantiated means the documented
`modules.protocols.mcp` config silently does nothing.

- **Derived-agent test:** the only workaround is for the consumer to
  re-implement the resolver + bridge lifecycle (`from_config` →
  `start()` → merge `tools()` into `Agent(tools=...)` → `close()` on
  exit) in their own `agent_factory`. That **couples every consumer to
  framework internals** and breaks the "reference it by name in YAML"
  promise. Hard framework defect.
- **How the fix helps derived agents:** declaring an MCP server in YAML
  Just Works — the subprocess spawns, tools appear in `agent.tools`, and
  the bridge is closed on agent exit, with zero hand-rolled wiring. It
  restores the config-driven, plug-and-play contract for the whole
  `modules.protocols[*]` category (MCP now, A2A next). Fixing this is
  what makes bug-012/013/014/015/017 reachable and worth fixing at all.

## Notes

- **Verified 2026-06-02:** exhaustive grep of `agentforge/` and
  `agentforge_core/` finds **zero** `MCPBridge` references; `protocols`
  is touched only by *validation* (`module_schemas.py:79-80`), never
  instantiated; `build_tools_from_config` exists but isn't even called by
  `build_agent_from_config`. The bug is real and central.
- Found while implementing a consumer's tool catalog. Reported alongside
  bug-009 and bug-010 — all surface only on live integration.
- downstream consumers ship local wiring in `agent_factory.py` that calls
  `MCPBridge.from_config()` manually. They'll remove the workaround when
  the runtime adopts the fix above.
