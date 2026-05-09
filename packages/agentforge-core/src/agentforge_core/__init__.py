"""AgentForge core — stable contracts (ABCs, value types).

Per ADR-0007, this package's public surface is the framework's locked
contract layer. Adding a method to an ABC is a major version bump.

This module re-exports every public symbol so consumers can import
from `agentforge_core` directly. Submodules (`agentforge_core.values`,
`agentforge_core.production`, etc.) remain part of the public surface
for granular imports.
"""

from __future__ import annotations

from agentforge_core.production import (
    AgentForgeError,
    BudgetExceeded,
    BudgetPolicy,
    CapabilityNotSupported,
    GuardrailViolation,
    ModuleError,
    ProviderError,
    RunContext,
    RunIdFilter,
    bind_run,
    current_run,
    install_run_id_filter,
    new_run,
    reset_run,
    uninstall_run_id_filter,
)
from agentforge_core.values import (
    AgentState,
    Claim,
    FinishReason,
    LLMResponse,
    Message,
    MessageRole,
    RunResult,
    Step,
    StepKind,
    StopReason,
    TokenUsage,
    ToolCall,
    ToolSpec,
)

__version__ = "0.0.0"

__all__ = [
    # Errors
    "AgentForgeError",
    "AgentState",
    "BudgetExceeded",
    "BudgetPolicy",
    "CapabilityNotSupported",
    "Claim",
    "FinishReason",
    "GuardrailViolation",
    "LLMResponse",
    "Message",
    "MessageRole",
    "ModuleError",
    "ProviderError",
    "RunContext",
    "RunIdFilter",
    "RunResult",
    "Step",
    "StepKind",
    "StopReason",
    "TokenUsage",
    "ToolCall",
    "ToolSpec",
    "__version__",
    "bind_run",
    "current_run",
    "install_run_id_filter",
    "new_run",
    "reset_run",
    "uninstall_run_id_filter",
]
