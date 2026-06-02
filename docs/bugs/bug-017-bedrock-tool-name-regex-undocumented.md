---
status: open
severity: P2
found-in: v0.2.3
found-via: live integration of a Bedrock-backed MCP agent (Khemchand Joshi, 2026-05-27)
---

# bug-017 — Bedrock's tool-name regex `[a-zA-Z0-9_-]+` is undocumented in the framework

## Symptom

Naming tools or MCP servers with dots, slashes, colons, or any
character outside `[a-zA-Z0-9_-]` produces a runtime validation error
from Bedrock on the first LLM call:

```
ProviderError: Bedrock validation: Value 'kb.search' at
'toolConfig.tools.<i>.member.toolSpec.name' failed to satisfy
constraint: Member must satisfy regular expression pattern:
[a-zA-Z0-9_-]+
```

The constraint comes from AWS Bedrock Converse, not the framework —
but no docstring, no runbook, no template README mentions it. Every
consumer who picks expressive tool names (`kb.search`, `metadata.list`,
`questions.generate`) hits this on day 1 with the Bedrock provider.

## Why this is a framework concern (not just AWS docs)

- The framework's MCP adapter joins server + tool with `.` (bug-012),
  which is silently illegal on Bedrock. Consumers who follow runbook
  09 with the Bedrock provider hit this without writing any
  illegally-named tool themselves.
- Other providers may not validate as strictly. Tools that work in
  CI tests (mocked LLM client) and prod with Anthropic-direct will
  break the moment a consumer swaps `model:` to `bedrock:`. Silent
  vendor-swap regression is exactly what "vendor-agnostic providers"
  is supposed to prevent.

## Fix proposal

Two layers of defense:

1. **Document the regex.** (Note: the runbooks the original draft
   referenced — "02 Add a tool", "09 Add MCP servers", "13 multi-provider"
   — **do not exist**; the docs tree is organised as `feat-NNN` specs,
   ADRs, and design docs, with no runbook directory.) Document the
   constraint where tool/provider naming actually lives:
   - feat-004 (tools system) spec + the `@tool` decorator docstring
   - feat-003 (LLM provider abstraction) spec, as a cross-provider gotcha
   - feat-013 (MCP) spec, since server + tool names both feed the
     qualified name (bug-012)
   - the scaffold templates' README where tool naming is shown
2. **Add a defensive validator** in the framework's Bedrock provider:
   when constructing `_build_converse_request`, scan all tool specs
   and raise a clear `BedrockToolNameInvalid("name 'X' does not match
   pattern [a-zA-Z0-9_-]+; valid sample: 'kb_search'")` error before
   the request leaves the process. That converts a remote validation
   error into a local one with a useful message and a fix suggestion.

The same pattern likely applies to other strict providers; the
framework's vendor-agnostic story works best when "valid on provider
A, valid on provider B" is enforced at the framework's name-check
boundary.

## Workaround

- Use only `[a-zA-Z0-9_-]+` in tool names and MCP server names.
- For the framework-generated MCP adapter naming, see bug-012.

## Framework-level vs derived-agent-level

**Framework.** The framework's selling point is vendor-agnostic
providers: the same `ToolSpec` flowing to any `model:` string. That
promise makes the framework responsible for surfacing cross-provider
name-legality at its own boundary.

- **Derived-agent test:** a name that's legal on the mocked CI client
  and Anthropic-direct but illegal on Bedrock is a regression the
  consumer *cannot see* until runtime on one specific vendor. They can't
  defend against an undocumented AWS regex they don't know exists →
  framework owns it. (This is the weaker of the two layers — naming
  tools legally is partly on the consumer — but converting a remote error
  into a local, actionable one is squarely the provider adapter's job.)
- **How the fix helps derived agents:** a local
  `BedrockToolNameInvalid("name 'kb.search' invalid; try 'kb_search'")`
  raised before the request leaves the process turns a cryptic remote
  `ProviderError` into an actionable, pre-flight error — and the same
  validator catches bug-012's adapter-generated names as a side effect.

## Notes

- **Verified:** no provider or core code validates tool names against any
  regex today (`agentforge-bedrock/client.py:339-342` passes `t.name`
  verbatim; `ToolSpec.name` and the `@tool` decorator have no name
  validator). The constraint appears in no docstring, spec, or template.
- P2 on its own (the remote message is at least specific). P0s elsewhere
  catch the immediate impact (bug-012 for MCP, bug-009 for ReAct).
- **Overlaps bug-012:** a Bedrock-side validator would catch bug-012's
  dotted names even before the separator fix lands — complementary, not
  duplicate. bug-012 fixes the framework's *own* name generation; bug-017
  adds the defensive net + docs for *all* (incl. consumer-authored) names.
- Discovered when a downstream consumer renamed 13 tools from dotted
  (`kb.search`) to underscored (`kb_search`) form — mechanical but
  unexpected mid-implementation.
