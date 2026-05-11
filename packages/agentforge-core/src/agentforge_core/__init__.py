"""AgentForge core — stable contracts (ABCs, value types).

Per ADR-0007, this package's public surface is the framework's locked
contract layer. Adding a method to an ABC is a major version bump.

This module re-exports every public symbol so consumers can import
from `agentforge_core` directly. Submodules (`agentforge_core.contracts`,
`agentforge_core.values`, `agentforge_core.production`) remain part of
the public surface for granular imports.
"""

from __future__ import annotations

from agentforge_core.contracts import (
    EmbeddingClient,
    EvalResult,
    Evaluator,
    Finding,
    FindingRenderer,
    GraphStore,
    LLMClient,
    MemoryStore,
    ReasoningStrategy,
    Tool,
    VectorStore,
)
from agentforge_core.production import (
    AgentForgeError,
    AuthenticationError,
    BudgetExceeded,
    BudgetPolicy,
    CapabilityNotSupported,
    GuardrailViolation,
    ModelNotFoundError,
    ModuleError,
    ProviderError,
    RateLimitError,
    RunContext,
    RunIdFilter,
    ServiceError,
    TimeoutError,
    bind_run,
    current_run,
    install_run_id_filter,
    new_run,
    reset_run,
    uninstall_run_id_filter,
)

# Imported from the submodule directly (not via production/__init__)
# to avoid a circular import — see the comment in production/__init__.py
# for the chain. This import runs *after* production finishes, so
# LLMClient is already available.
from agentforge_core.production.fallback import FallbackChain
from agentforge_core.resolver import (
    Resolver,
    parse_model_string,
    register,
    register_embedding_provider,
    register_provider,
)
from agentforge_core.values import (
    AgentState,
    Claim,
    EmbeddingResponse,
    FinishReason,
    GraphEdge,
    GraphNode,
    GraphPattern,
    GraphSegment,
    LLMResponse,
    Message,
    MessageRole,
    Path,
    RunResult,
    Step,
    StepKind,
    StopReason,
    StreamChunk,
    StreamChunkKind,
    TokenUsage,
    ToolCall,
    ToolSpec,
    VectorItem,
    VectorMatch,
)

__version__ = "0.0.0"

__all__ = [
    "AgentForgeError",
    "AgentState",
    "AuthenticationError",
    "BudgetExceeded",
    "BudgetPolicy",
    "CapabilityNotSupported",
    "Claim",
    "EmbeddingClient",
    "EmbeddingResponse",
    "EvalResult",
    "Evaluator",
    "FallbackChain",
    "Finding",
    "FindingRenderer",
    "FinishReason",
    "GraphEdge",
    "GraphNode",
    "GraphPattern",
    "GraphSegment",
    "GraphStore",
    "GuardrailViolation",
    "LLMClient",
    "LLMResponse",
    "MemoryStore",
    "Message",
    "MessageRole",
    "ModelNotFoundError",
    "ModuleError",
    "Path",
    "ProviderError",
    "RateLimitError",
    "ReasoningStrategy",
    "Resolver",
    "RunContext",
    "RunIdFilter",
    "RunResult",
    "ServiceError",
    "Step",
    "StepKind",
    "StopReason",
    "StreamChunk",
    "StreamChunkKind",
    "TimeoutError",
    "TokenUsage",
    "Tool",
    "ToolCall",
    "ToolSpec",
    "VectorItem",
    "VectorMatch",
    "VectorStore",
    "__version__",
    "bind_run",
    "current_run",
    "install_run_id_filter",
    "new_run",
    "parse_model_string",
    "register",
    "register_embedding_provider",
    "register_provider",
    "reset_run",
    "uninstall_run_id_filter",
]
