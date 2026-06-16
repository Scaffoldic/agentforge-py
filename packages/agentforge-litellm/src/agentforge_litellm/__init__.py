"""`agentforge-litellm` — LiteLLM router-based LLM provider."""

from __future__ import annotations

# Version is sourced from the installed distribution metadata so it can
# never drift from pyproject.toml (bug-024).
from importlib.metadata import PackageNotFoundError as _PkgNotFound
from importlib.metadata import version as _dist_version

from agentforge_litellm._runner import LiteLLMRunner
from agentforge_litellm.client import LiteLLMClient

try:
    __version__ = _dist_version("agentforge-litellm")
except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = ["LiteLLMClient", "LiteLLMRunner", "__version__"]
