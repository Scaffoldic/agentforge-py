"""`agentforge-voyage` — Voyage AI embedding provider."""

from __future__ import annotations

from agentforge_voyage._runner import VoyageRunner
from agentforge_voyage.embedding import VoyageEmbeddingClient

__version__ = "0.2.1"

__all__ = ["VoyageEmbeddingClient", "VoyageRunner", "__version__"]
