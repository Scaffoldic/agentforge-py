"""Configuration loader for `agentforge.yaml`.

feat-001 ships only the partial schema that feat-001's surface needs.
feat-012 ships the full schema with module / observability / providers
sections. Both phases use the same loader; the schema grows additively.
"""

from __future__ import annotations

from agentforge.config.loader import load_config
from agentforge.config.schema import AgentConfig, AgentForgeConfig, LoggingConfig

__all__ = [
    "AgentConfig",
    "AgentForgeConfig",
    "LoggingConfig",
    "load_config",
]
