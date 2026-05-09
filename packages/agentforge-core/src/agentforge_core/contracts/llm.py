"""`LLMClient` — the locked LLM provider abstraction.

feat-001 ships the minimum surface: `call`, `close`, and capability
introspection. feat-003 extends with `call_with_cache`,
`call_with_thinking`, `stream`, and the `EmbeddingClient` ABC, all
behind capability flags so the surface stays additive (per ADR-0009).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentforge_core.values.messages import LLMResponse, Message, ToolSpec


class LLMClient(ABC):
    """Provider-agnostic chat-completion client.

    Every provider module implements this ABC. Reasoning strategies
    consume `LLMClient` (not the concrete provider type) so a string-id
    swap (`"anthropic:..."` → `"bedrock:..."`) requires no code change.
    """

    @abstractmethod
    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        """Issue a single chat-completion request.

        Args:
            system: System prompt.
            messages: Conversation turns to date.
            tools: Optional tool catalogue exposed to the LLM.

        Returns:
            The provider's response, normalised to `LLMResponse`.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release any resources (HTTP clients, connection pools)."""

    def capabilities(self) -> set[str]:
        """Optional capabilities this provider supports.

        Default empty set. Subclasses override to declare capabilities
        from the closed vocabulary (per ADR-0009): "caching", "thinking",
        "streaming", "tools", "json_mode", "vision", "parallel_tools".

        Returns:
            Set of capability names.
        """
        return set()

    def supports(self, capability: str) -> bool:
        """True if this client declares the given capability."""
        return capability in self.capabilities()
