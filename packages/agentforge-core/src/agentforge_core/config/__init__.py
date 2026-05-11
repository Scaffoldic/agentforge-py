"""Configuration system for AgentForge (feat-012).

`agentforge.yaml` is the single source of truth for an agent's
runtime wiring. This package ships:

- The locked **root schema** (`AgentForgeConfig` + sub-models).
- The **loader** (`load_config`) with env-var interpolation,
  layered env files, dotted-path overrides, and module-side
  schema validation.

Per ADR-0013, configuration is *data* — no Jinja, no dynamic
imports, no arbitrary template logic. Env-var interpolation
(`${VAR}`, `${VAR:default}`, `${VAR:?error}`, `$$`) and
schema-validated YAML are the only ways content flows into the
runtime.

The schema is locked under ADR-0007: adding a field is a minor
bump; removing or renaming requires a major bump.
"""

from __future__ import annotations

from agentforge_core.config.loader import load_config, parse_overrides
from agentforge_core.config.schema import (
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
