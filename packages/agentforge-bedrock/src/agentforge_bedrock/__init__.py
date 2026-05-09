"""AgentForge — AWS Bedrock provider.

Implements `LLMClient` (and, in feat-003 chunk 5, `EmbeddingClient`)
over AWS Bedrock. Use via `Agent(model="bedrock:<model-id>")` or by
constructing `BedrockClient(model_id=...)` directly.

Per ADR-0014 every code path is async — the driver uses `aioboto3`,
never sync `boto3`, so it never blocks the event loop.
"""

from __future__ import annotations

from agentforge_bedrock.client import BedrockClient

__version__ = "0.0.0"

__all__ = ["BedrockClient", "__version__"]
