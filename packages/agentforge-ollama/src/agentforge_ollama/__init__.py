"""`agentforge-ollama` — Ollama local LLM + embedding provider."""

from __future__ import annotations

# Version is sourced from the installed distribution metadata so it can
# never drift from pyproject.toml (bug-024).
from importlib.metadata import PackageNotFoundError as _PkgNotFound
from importlib.metadata import version as _dist_version

from agentforge_ollama._runner import OllamaRunner
from agentforge_ollama.client import OllamaClient
from agentforge_ollama.embedding import OllamaEmbeddingClient

try:
    __version__ = _dist_version("agentforge-ollama")
except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = [
    "OllamaClient",
    "OllamaEmbeddingClient",
    "OllamaRunner",
    "__version__",
]
