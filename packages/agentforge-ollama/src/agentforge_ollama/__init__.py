"""`agentforge-ollama` — Ollama local LLM + embedding provider."""

from __future__ import annotations

from agentforge_ollama._runner import OllamaRunner
from agentforge_ollama.client import OllamaClient
from agentforge_ollama.embedding import OllamaEmbeddingClient

__version__ = "0.2.0"

__all__ = [
    "OllamaClient",
    "OllamaEmbeddingClient",
    "OllamaRunner",
    "__version__",
]
