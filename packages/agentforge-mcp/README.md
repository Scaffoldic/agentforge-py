# agentforge-mcp

[Model Context Protocol](https://modelcontextprotocol.io)
integration for AgentForge (feat-013).

Adds the `mcp` protocol entry to `agentforge.yaml`:

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
          - name: my-internal-tools
            transport: http
            url: "http://internal:8080/mcp"
        expose:
          enabled: true
          transport: stdio
          tools: ["lookup_user", "create_ticket"]
```

```bash
agentforge add module mcp
```

Each consumed MCP server's tools land in `agent.tools` with a
server-name prefix (`filesystem__read_file`,
`github__create_issue`). The separator is a double underscore so
the name stays legal under every provider's tool-name charset
(`^[a-zA-Z0-9_-]{1,64}$`). When `expose.enabled` is set, the agent
runs an MCP server alongside; other agents (Claude Desktop,
Cursor, other MCP clients) can call into it.
