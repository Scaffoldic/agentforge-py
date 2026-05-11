# 09 — Add MCP servers

> **Goal:** consume Anthropic Model Context Protocol tool servers
> as if they were native tools, or expose your agent's tools as
> an MCP server.
> **Time:** ~10 minutes.
> **Prereqs:** runbook 02.

## TL;DR

```yaml
# agentforge.yaml
modules:
  protocols:
    - name: mcp
      config:
        servers:
          - command: ["uv", "run", "filesystem-mcp"]
            cwd: ./mcp-servers
        expose_local_tools: true     # turn this agent into an MCP server too
```

```bash
agentforge add module mcp
```

## Step by step

1. **Install the MCP module.** `agentforge add module mcp` —
   adds `agentforge-mcp` to dependencies and registers the
   protocol under `modules.protocols`.
2. **Declare upstream servers.** `servers:` is a list of command
   specifications. Each spawns on agent start; the framework
   handles handshake and tool discovery.
3. **Restart the agent.** Discovered MCP tools appear in the
   agent's tool list automatically; the LLM sees their schemas
   alongside framework-native tools.
4. **(Optional) Expose your tools.** `expose_local_tools: true`
   makes this agent's tools available as an MCP server, so other
   agents (or Claude Desktop) can call into it.
5. **Verify** with `agentforge list tools` — MCP tools have an
   `mcp:` prefix in the resolver listing.

## Variations

- **Per-server allowlist** — `servers[].tools: ["read_file",
  "list_directory"]` restricts what gets exposed from each
  server. Use this for least-privilege.
- **Auth headers** — `servers[].auth.bearer: "${MCP_TOKEN}"` for
  hosted MCP servers behind auth.
- **Capability negotiation** — `expose_local_tools.exclude:
  [...]` strips internal tools from the exposed MCP surface.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| MCP server fails to spawn | wrong command path | check `agentforge config show --resolved` matches your shell's view |
| Tools not visible to LLM | discovery race | bump `servers[].start_timeout` (default 5s) |
| Tool calls hang | MCP server blocking on stdio | check the server's logs; MCP requires line-delimited JSON |
| `permission denied` from exposed server | client passed a tool not in allowlist | add to `expose_local_tools.tools` or remove the deny |

## Related

- Runbook 02 — Add a (native) tool
- Runbook 11 — Add safety guardrails (MCP tools go through the
  same gates)
- Feature spec: `docs/features/feat-013-mcp-integration.md`

> **Note:** MCP integration is feat-013. If this framework
> version pre-dates the module shipping, install
> `agentforge-mcp` manually from the framework repo's
> `packages/`.

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
