"""`EmbeddingClient` — locked embeddings provider abstraction.

Embedding providers (Bedrock Titan / Cohere, OpenAI, etc.) implement
this ABC. The vector store / retrieval layer (feat-007) consumes
`EmbeddingClient`, never the concrete driver type, so swapping
providers is a string-id swap.

Per ADR-0007 the surface is locked at v0.1: adding a method is a
major version bump. Optional capabilities (e.g. multimodal embeddings)
are layered the same way as on `LLMClient` — declared in
`capabilities()` and gated via `supports()`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentforge_core.values.messages import EmbeddingResponse


class EmbeddingClient(ABC):
    """Provider-agnostic text-embedding client.

    Implementations:
      - normalise the provider's response into `EmbeddingResponse`
      - declare the model's vector dimensionality up front via
        `dimensions()` so callers can size storage before the call
      - compute `cost_usd` from token usage and a per-model price
        table inside the driver (consistent with `LLMClient`)
    """

    @abstractmethod
    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        """Embed a batch of texts.

        Args:
            texts: One or more texts to embed. Empty list raises
                `ValueError` (no provider supports zero-length batches
                and the cost would be ambiguous).

        Returns:
            `EmbeddingResponse` carrying one vector per input text in
            input order. Every vector has length `self.dimensions()`.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release any resources (HTTP clients, connection pools)."""

    @abstractmethod
    def dimensions(self) -> int:
        """The vector dimensionality every `embed()` call returns.

        Drivers declare this without a network round-trip — it is a
        property of the configured model. Callers use this to size
        storage (e.g. vector-store column widths) before the first
        embed call.
        """

    def capabilities(self) -> set[str]:
        """Optional capabilities this driver supports.

        Default empty set. Closed vocabulary (additions are minor
        bumps): `"multimodal"` (image / audio inputs in addition to
        text), `"matryoshka"` (truncatable variable-length vectors).
        """
        return set()

    def supports(self, capability: str) -> bool:
        """True if this client declares the given capability."""
        return capability in self.capabilities()
