"""`agentforge-openai` — OpenAI LLM + embedding provider."""

from __future__ import annotations

# Version is sourced from the installed distribution metadata so it can
# never drift from pyproject.toml (bug-024).
from importlib.metadata import PackageNotFoundError as _PkgNotFound
from importlib.metadata import version as _dist_version

from agentforge_openai._runner import OpenAIRunner
from agentforge_openai.client import OpenAIClient
from agentforge_openai.embedding import OpenAIEmbeddingClient

try:
    __version__ = _dist_version("agentforge-openai")
except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = [
    "OpenAIClient",
    "OpenAIEmbeddingClient",
    "OpenAIRunner",
    "__version__",
]
