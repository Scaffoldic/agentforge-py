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
or use the `agentforge-py[<extra>]` install (per ADR-0003).

See the project docs at `docs/README.md` (in the design workspace) and
the per-feature specs under `docs/features/`.
"""

from __future__ import annotations

from agentforge_core import FallbackChain

# feat-018: importing `agentforge.guardrails` here triggers the
# module-side `@register(...)` decorators on `PromptInjectionBasic`,
# `PIIRedactBasic`, `CapabilityCheck`, and `Allowlist` so they're
# resolvable by name from `agentforge.yaml` without an explicit
# import in the consumer.
import agentforge.guardrails  # noqa: F401
from agentforge._tools import tool
from agentforge.agent import Agent
from agentforge.auth import EnvBearerAuth
from agentforge.config import AgentForgeConfig, load_config
from agentforge.findings import (
    MultiSpanFinding,
    NarrativeFinding,
    Patch,
    PatchFinding,
    SimpleFinding,
    Span,
)
from agentforge.memory import InMemoryGraphStore, InMemoryStore, InMemoryVectorStore
from agentforge.pipeline import (
    Pipeline,
    PipelineFailure,
    PipelineFindingsTool,
    PipelineResult,
    Task,
)
from agentforge.renderers import (
    MarkdownRenderer,
    MissingRendererError,
    PatchApplierRenderer,
    RendererRegistry,
    ScorecardRenderer,
    SpanTableRenderer,
)
from agentforge.resolver_register import register_task
from agentforge.retrieval import Retriever
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

__version__ = "0.2.3"

__all__ = [
    "RUNTIME_KEY",
    "Agent",
    "AgentForgeConfig",
    "EnvBearerAuth",
    "FallbackChain",
    "InMemoryGraphStore",
    "InMemoryStore",
    "InMemoryVectorStore",
    "MarkdownRenderer",
    "MissingRendererError",
    "MultiAgentSupervisor",
    "MultiSpanFinding",
    "NarrativeFinding",
    "Patch",
    "PatchApplierRenderer",
    "PatchFinding",
    "Pipeline",
    "PipelineFailure",
    "PipelineFindingsTool",
    "PipelineResult",
    "Plan",
    "PlanExecuteLoop",
    "PlanStep",
    "ReActLoop",
    "RendererRegistry",
    "Retriever",
    "RuntimeContext",
    "ScorecardRenderer",
    "SimpleFinding",
    "Span",
    "SpanTableRenderer",
    "StrategyBase",
    "Task",
    "TreeOfThoughts",
    "__version__",
    "get_runtime",
    "load_config",
    "register_task",
    "tool",
]
