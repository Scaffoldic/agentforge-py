"""`agentforge-a2a` — A2A protocol support for AgentForge (feat-014).

Public surface:

- `agent_call(target, payload, *, peers, ...)` — outgoing A2A
  client.
- `A2APeer` — per-peer config + runner.
- `A2AServer(agent, ..., auth, endpoints)` — FastAPI server
  exposing this agent as an A2A peer.
- `A2ABridge.from_config(config, ...)` — orchestrator that
  wires both halves from a config dict.
- `BearerAuth` / `MutualTLSAuth` — client-side credential
  builders. (Server-side bearer validation uses the canonical
  `agentforge_core.contracts.auth.AuthPolicy`.)
"""

from __future__ import annotations

from agentforge_a2a.auth import BearerAuth, ClientAuth, MutualTLSAuth, build_outgoing_auth
from agentforge_a2a.bridge import A2ABridge
from agentforge_a2a.client import A2APeer, agent_call
from agentforge_a2a.config import A2AConfig
from agentforge_a2a.server import A2AServer
from agentforge_a2a.values import (
    A2AEndpointConfig,
    A2AExposeConfig,
    A2APeerConfig,
    A2AResponse,
)

__all__ = [
    "A2ABridge",
    "A2AConfig",
    "A2AEndpointConfig",
    "A2AExposeConfig",
    "A2APeer",
    "A2APeerConfig",
    "A2AResponse",
    "A2AServer",
    "BearerAuth",
    "ClientAuth",
    "MutualTLSAuth",
    "agent_call",
    "build_outgoing_auth",
]
