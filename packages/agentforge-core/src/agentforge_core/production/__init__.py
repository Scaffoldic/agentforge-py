"""Production-rails primitives.

Owned by the framework (per ADR-0010): every agent has these wired by
default. Includes per-run cost guarding (`BudgetPolicy`), correlation
context (`RunContext`, `current_run`), structured logging filter
(`RunIdFilter`), and the framework's exception hierarchy.
"""

from __future__ import annotations

from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.production.exceptions import (
    AgentForgeError,
    BudgetExceeded,
    CapabilityNotSupported,
    GuardrailViolation,
    ModuleError,
    ProviderError,
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
    "BudgetExceeded",
    "BudgetPolicy",
    "CapabilityNotSupported",
    "GuardrailViolation",
    "ModuleError",
    "ProviderError",
    "RunContext",
    "RunIdFilter",
    "bind_run",
    "current_run",
    "install_run_id_filter",
    "new_run",
    "reset_run",
    "uninstall_run_id_filter",
]
