"""Locked contracts — ABCs and the `Finding` Protocol.

Per ADR-0007, these are the framework's stable surface. Adding a method
to an ABC is a major version bump. Modules implement these; the runtime
consumes them by reference to the abstraction, never the implementation.
"""

from __future__ import annotations

from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.evaluator import EvalResult, Evaluator
from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.graph_store import GraphStore
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.contracts.tool import Tool
from agentforge_core.contracts.vector_store import VectorStore

__all__ = [
    "EmbeddingClient",
    "EvalResult",
    "Evaluator",
    "Finding",
    "GraphStore",
    "LLMClient",
    "MemoryStore",
    "ReasoningStrategy",
    "Tool",
    "VectorStore",
]
