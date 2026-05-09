"""AgentForge — open-source plug-and-play framework for production AI agents.

This package is the default runtime. It ships:

  - The `Agent` orchestrator (lands later in feat-001).
  - `InMemoryStore` — process-local default `MemoryStore` so a fresh
    agent has persistence wired without external infra.

For provider clients, persistence drivers, MCP, observability backends,
and safety modules, install the corresponding `agentforge-<X>` packages
or use the `agentforge[<extra>]` install (per ADR-0003).

See the project docs at `docs/README.md` (in the design workspace) and
the per-feature specs under `docs/features/`.
"""

from __future__ import annotations

from agentforge.memory import InMemoryStore

__version__ = "0.0.0"

__all__ = [
    "InMemoryStore",
    "__version__",
]
