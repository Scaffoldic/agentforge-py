"""Locked value types — Pydantic v2 models the framework's contracts use.

Per ADR-0007, these shapes are part of the framework's stable surface;
adding a field requires a minor bump, removing or renaming a field
requires a major bump.
"""

from __future__ import annotations

from agentforge_core.values.claim import Claim
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    MessageRole,
    StopReason,
    TokenUsage,
    ToolCall,
    ToolSpec,
)
from agentforge_core.values.state import (
    AgentState,
    FinishReason,
    RunResult,
    Step,
    StepKind,
)

__all__ = [
    "AgentState",
    "Claim",
    "FinishReason",
    "LLMResponse",
    "Message",
    "MessageRole",
    "RunResult",
    "Step",
    "StepKind",
    "StopReason",
    "TokenUsage",
    "ToolCall",
    "ToolSpec",
]
