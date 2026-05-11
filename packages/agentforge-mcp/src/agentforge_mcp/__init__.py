"""MCP integration for AgentForge (feat-013).

Two surfaces:

- `MCPServerClient` connects to an external MCP server and
  adapts its tools as `MCPToolAdapter` instances that look like
  any other `agentforge.Tool` to the agent.
- `MCPServer` (chunk 3) exposes a list of `Tool` instances as
  an MCP server so other agents can consume them.
- `MCPBridge` (chunk 4) orchestrates a set of clients + an
  optional server, wired from `modules.protocols.mcp` config.
"""

from __future__ import annotations

from agentforge_mcp.adapter import MCPToolAdapter
from agentforge_mcp.client import MCPServerClient

__all__ = ["MCPServerClient", "MCPToolAdapter"]
