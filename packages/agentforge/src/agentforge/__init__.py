"""AgentForge — open-source plug-and-play framework for production AI agents.

This package is the default runtime. It ships:

  - The `Agent` orchestrator (locked constructor surface per feat-001).
  - `InMemoryStore` — process-local default `MemoryStore` so a fresh
    agent has persistence wired without external infra.
  - The configuration loader (`load_config`).
  - The reasoning-strategy infrastructure: `RuntimeContext`,
    `StrategyBase`, `get_runtime`, `ReActLoop` (feat-002).

For provider clients, persistence drivers, MCP, observability backends,
and safety modules, install the corresponding `agentforge-<X>` packages
or use the `agentforge[<extra>]` install (per ADR-0003).

See the project docs at `docs/README.md` (in the design workspace) and
the per-feature specs under `docs/features/`.
"""

from __future__ import annotations

from agentforge.agent import Agent
from agentforge.config import AgentForgeConfig, load_config
from agentforge.memory import InMemoryStore
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge.strategies import (
    MultiAgentSupervisor,
    Plan,
    PlanExecuteLoop,
    PlanStep,
    ReActLoop,
    StrategyBase,
    TreeOfThoughts,
    get_runtime,
)

__version__ = "0.0.0"

__all__ = [
    "RUNTIME_KEY",
    "Agent",
    "AgentForgeConfig",
    "InMemoryStore",
    "MultiAgentSupervisor",
    "Plan",
    "PlanExecuteLoop",
    "PlanStep",
    "ReActLoop",
    "RuntimeContext",
    "StrategyBase",
    "TreeOfThoughts",
    "__version__",
    "get_runtime",
    "load_config",
]
