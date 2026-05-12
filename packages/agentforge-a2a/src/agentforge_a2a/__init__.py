"""`agentforge-a2a` — A2A protocol support for AgentForge (feat-014).

Public surface (chunks 3-4):
- `agent_call(target, payload, *, ...)` — outgoing A2A client.
- `A2APeer` — per-peer config + runner.
- `A2AServer(agent, ...)` — FastAPI server exposing this agent.
- `A2ABridge.from_config(config)` — orchestrator.
- `BearerAuth` / `MutualTLSAuth` — client-side credentials.
"""

from __future__ import annotations

from agentforge_a2a.auth import BearerAuth, ClientAuth, MutualTLSAuth, build_outgoing_auth
from agentforge_a2a.client import A2APeer, agent_call
from agentforge_a2a.values import (
    A2AEndpointConfig,
    A2AExposeConfig,
    A2APeerConfig,
    A2AResponse,
)

__all__ = [
    "A2AEndpointConfig",
    "A2AExposeConfig",
    "A2APeer",
    "A2APeerConfig",
    "A2AResponse",
    "BearerAuth",
    "ClientAuth",
    "MutualTLSAuth",
    "agent_call",
    "build_outgoing_auth",
]
