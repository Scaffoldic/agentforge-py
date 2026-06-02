---
status: open
severity: P0
found-in: v0.2.3
found-via: live integration of a Bedrock-backed MCP agent (Khemchand Joshi, 2026-05-27)
---

# bug-012 — `MCPToolAdapter` qualified name uses `.` separator → Bedrock rejects every MCP tool

## Symptom

Every Bedrock-backed agent with an MCP server attached fails on the first
LLM call with `toolConfig.tools[i].member.toolSpec.name` validation error:

```
Bedrock validation: Value 'myserver.my_tool' at
'toolConfig.tools.8.member.toolSpec.name' failed to satisfy constraint:
Member must satisfy regular expression pattern: [a-zA-Z0-9_-]+
```

## Root cause

`agentforge_mcp/adapter.py::build_adapter` (lines 33-46):

```python
qualified_name = f"{server_name}.{descriptor.name}"
```

The dot is illegal in Bedrock Converse tool names (regex
`[a-zA-Z0-9_-]+`). Pattern bites every consumer using `bedrock:` provider.

## Fix proposal

Use a Bedrock-safe separator. Two options:

1. `"__"` (double underscore) — keeps the disambiguation between
   servers, stays legal under Bedrock + OpenAI tool-name rules.
2. Single underscore (`"_"`) — simpler; risks collision if tools
   already use `_`.

Recommend option 1. Update the docstring and any callers that parse
the qualified name.

## Workaround

Downstream consumers can monkey-patch `build_adapter` (and the cached
re-export in `agentforge_mcp.client`) to drop or replace the separator.
downstream consumers ship such a patch.

## Framework-level vs derived-agent-level

**Framework.** `build_adapter` is framework code that *owns* the
construction of the public tool name, and it is the framework's own
provider clients (`agentforge-{anthropic,openai,bedrock}/client.py`,
which all emit `"name": t.name` verbatim — verified) that ship that name
to provider APIs with a known charset constraint.

- **Derived-agent test:** a consumer *cannot* fix this without
  monkey-patching `build_adapter` and the cached re-export in
  `agentforge_mcp.client` — i.e. reaching into framework internals. Fails
  the test → framework defect.
- **How the fix helps derived agents:** every consumer using `bedrock:`
  (or any provider enforcing `[a-zA-Z0-9_-]`) gets working MCP tools with
  zero monkey-patching, and the framework keeps its vendor-agnostic
  promise — a name that works on one provider works on all of them.

## Notes

- See related **bug-020** (runtime doesn't wire the MCP bridge at all).
  With bug-020 fixed but bug-012 unfixed, MCP is still unusable on
  Bedrock. (The "bug-011" in an earlier draft referred to the wiring bug
  before it was renumbered to bug-020.)
- **Verified** to affect OpenAI / Anthropic-direct the same way — all
  three provider clients pass `t.name` straight to the wire and each API
  validates `^[a-zA-Z0-9_-]{1,64}$`. Bedrock is just where consumers hit
  it first. See bug-017 for the cross-provider validator that catches
  this class locally.
