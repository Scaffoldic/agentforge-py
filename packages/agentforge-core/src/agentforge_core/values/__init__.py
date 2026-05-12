"""Locked value types — Pydantic v2 models the framework's contracts use.

Per ADR-0007, these shapes are part of the framework's stable surface;
adding a field requires a minor bump, removing or renaming a field
requires a major bump.
"""

from __future__ import annotations

from agentforge_core.values.chat import (
    ChatChunk,
    ChatChunkKind,
    ChatResponse,
    ChatRole,
    ChatTurn,
    SessionInfo,
)
from agentforge_core.values.claim import Claim
from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    GraphSegment,
    Path,
)
from agentforge_core.values.manifest import (
    AppliedEnvVar,
    AppliedManifest,
    AppliedTemplate,
    EnvVarEntry,
    Manifest,
    TemplateFile,
)
from agentforge_core.values.messages import (
    EmbeddingResponse,
    LLMResponse,
    Message,
    MessageRole,
    StopReason,
    StreamChunk,
    StreamChunkKind,
    TokenUsage,
    ToolCall,
    ToolSpec,
)
from agentforge_core.values.module import ModuleInfo
from agentforge_core.values.pipeline import PipelineResult
from agentforge_core.values.state import (
    AgentState,
    FinishReason,
    RunResult,
    Step,
    StepKind,
)
from agentforge_core.values.vector import VectorItem, VectorMatch

__all__ = [
    "AgentState",
    "AppliedEnvVar",
    "AppliedManifest",
    "AppliedTemplate",
    "ChatChunk",
    "ChatChunkKind",
    "ChatResponse",
    "ChatRole",
    "ChatTurn",
    "Claim",
    "EmbeddingResponse",
    "EnvVarEntry",
    "FinishReason",
    "GraphEdge",
    "GraphNode",
    "GraphPattern",
    "GraphSegment",
    "LLMResponse",
    "Manifest",
    "Message",
    "MessageRole",
    "ModuleInfo",
    "Path",
    "PipelineResult",
    "RunResult",
    "SessionInfo",
    "Step",
    "StepKind",
    "StopReason",
    "StreamChunk",
    "StreamChunkKind",
    "TemplateFile",
    "TokenUsage",
    "ToolCall",
    "ToolSpec",
    "VectorItem",
    "VectorMatch",
]
