"""AgentForge — AWS Bedrock provider.

Implements `LLMClient` (and, in feat-003 chunk 5, `EmbeddingClient`)
over AWS Bedrock. Use via `Agent(model="bedrock:<model-id>")` or by
constructing `BedrockClient(model_id=...)` directly.

Per ADR-0014 every code path is async — the driver uses `aioboto3`,
never sync `boto3`, so it never blocks the event loop.
"""

from __future__ import annotations

# Version is sourced from the installed distribution metadata so it can
# never drift from pyproject.toml (bug-024).
from importlib.metadata import PackageNotFoundError as _PkgNotFound
from importlib.metadata import version as _dist_version

from agentforge_bedrock.client import BedrockClient, accumulate_stream
from agentforge_bedrock.embedding import BedrockEmbeddingClient

try:
    __version__ = _dist_version("agentforge-bedrock")
except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = [
    "BedrockClient",
    "BedrockEmbeddingClient",
    "__version__",
    "accumulate_stream",
]
