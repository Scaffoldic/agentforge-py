"""Configuration loader for `agentforge.yaml` — re-export from core.

feat-012 moved the canonical schema + loader to `agentforge-core`
so the resolver can compose module-side Pydantic schemas without
importing the runtime package. This module stays as a re-export
for the historical `from agentforge.config import ...` path.
"""

from __future__ import annotations

from agentforge_core.config import (
    AgentConfig,
    AgentForgeConfig,
    BudgetConfig,
    EvaluatorEntry,
    GraphModuleConfig,
    LoggingConfig,
    MemoryModuleConfig,
    ModuleEntry,
    ModulesConfig,
    ObservabilityEntry,
    OutputConfig,
    ProviderConfig,
    RetrieverModuleConfig,
    load_config,
    parse_overrides,
)

__all__ = [
    "AgentConfig",
    "AgentForgeConfig",
    "BudgetConfig",
    "EvaluatorEntry",
    "GraphModuleConfig",
    "LoggingConfig",
    "MemoryModuleConfig",
    "ModuleEntry",
    "ModulesConfig",
    "ObservabilityEntry",
    "OutputConfig",
    "ProviderConfig",
    "RetrieverModuleConfig",
    "load_config",
    "parse_overrides",
]
