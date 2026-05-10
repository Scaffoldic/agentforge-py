"""Production-rails primitives.

Owned by the framework (per ADR-0010): every agent has these wired by
default. Includes per-run cost guarding (`BudgetPolicy`), correlation
context (`RunContext`, `current_run`), structured logging filter
(`RunIdFilter`), cross-provider failover (`FallbackChain`), and the
framework's exception hierarchy.
"""

from __future__ import annotations

# `FallbackChain` is intentionally NOT re-exported here because it
# imports `LLMClient`, which would create a circular import:
# `agentforge_core/__init__.py` → contracts.llm (imports
# `CapabilityNotSupported` from `production.exceptions`) →
# triggers `production/__init__.py` → fallback (imports
# LLMClient still being loaded). Users reach FallbackChain via the
# top-level `from agentforge_core import FallbackChain` (loaded
# after `production` finishes), or directly via
# `agentforge_core.production.fallback`.
from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.production.exceptions import (
    AgentForgeError,
    AuthenticationError,
    BudgetExceeded,
    CapabilityNotSupported,
    GuardrailViolation,
    ModelNotFoundError,
    ModuleError,
    ProviderError,
    RateLimitError,
    ServiceError,
    TimeoutError,
)
from agentforge_core.production.log_filter import (
    RunIdFilter,
    install_run_id_filter,
    uninstall_run_id_filter,
)
from agentforge_core.production.run_context import (
    RunContext,
    bind_run,
    current_run,
    new_run,
    reset_run,
)

__all__ = [
    "AgentForgeError",
    "AuthenticationError",
    "BudgetExceeded",
    "BudgetPolicy",
    "CapabilityNotSupported",
    "GuardrailViolation",
    "ModelNotFoundError",
    "ModuleError",
    "ProviderError",
    "RateLimitError",
    "RunContext",
    "RunIdFilter",
    "ServiceError",
    "TimeoutError",
    "bind_run",
    "current_run",
    "install_run_id_filter",
    "new_run",
    "reset_run",
    "uninstall_run_id_filter",
]
