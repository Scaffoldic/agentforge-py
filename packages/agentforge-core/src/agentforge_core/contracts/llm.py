"""`LLMClient` — the locked LLM provider abstraction.

The mandatory surface is `call`, `close`, and capability introspection
(`capabilities` / `supports`). The optional surface — `call_with_cache`,
`call_with_thinking`, `stream` — is layered as default-raise methods so
the contract stays additive (per ADR-0009): drivers that don't support
a capability simply leave the default in place; consumers gate on
`client.supports("capability")` before invoking.

Capability vocabulary (closed enum, additions are minor bumps):
  - "tools"           — `tools=` argument honoured by `call`
  - "json_mode"       — provider returns guaranteed-valid JSON
  - "vision"          — multimodal input
  - "caching"         — `call_with_cache` works (prompt caching)
  - "thinking"        — `call_with_thinking` works (extended thinking)
  - "streaming"       — `stream` works
  - "parallel_tools"  — provider may emit multiple tool calls per turn
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from agentforge_core.production.exceptions import CapabilityNotSupported
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    StreamChunk,
    ToolSpec,
)


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
        from the closed vocabulary (per ADR-0009).

        Returns:
            Set of capability names.
        """
        return set()

    def supports(self, capability: str) -> bool:
        """True if this client declares the given capability."""
        return capability in self.capabilities()

    # ------------------------------------------------------------------
    # Optional capabilities — drivers override; default raise.
    # ------------------------------------------------------------------

    async def call_with_cache(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        cache_breakpoints: list[int],
    ) -> LLMResponse:
        """Call the model with explicit prompt-cache breakpoints.

        `cache_breakpoints` is a list of `messages` indices after which
        the provider should mark a cache point. Drivers that support
        prompt caching (Anthropic, Bedrock with Claude) honour this;
        every other driver leaves the default in place.

        Raises:
            CapabilityNotSupported: this driver did not declare
                `"caching"` in `capabilities()`.
        """
        raise CapabilityNotSupported(
            f"{type(self).__name__} does not support 'caching'. "
            f"Check client.supports('caching') before calling."
        )

    async def call_with_thinking(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        thinking_budget_tokens: int,
    ) -> LLMResponse:
        """Call the model with extended-thinking enabled.

        `thinking_budget_tokens` caps the model's internal reasoning
        budget. The returned `LLMResponse.usage.thinking_tokens`
        reports actual usage; the public `content` excludes the
        thinking trace.

        Raises:
            CapabilityNotSupported: this driver did not declare
                `"thinking"` in `capabilities()`.
        """
        raise CapabilityNotSupported(
            f"{type(self).__name__} does not support 'thinking'. "
            f"Check client.supports('thinking') before calling."
        )

    def stream(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream the model's response chunk-by-chunk.

        Returns an async iterator that yields `StreamChunk`s and
        terminates with exactly one `kind="stop"` chunk carrying final
        usage and cost. Synchronous in shape (returns an iterator) so
        the caller can pass it through pipes/transforms without an
        extra `await`.

        Raises:
            CapabilityNotSupported: this driver did not declare
                `"streaming"` in `capabilities()`.
        """
        raise CapabilityNotSupported(
            f"{type(self).__name__} does not support 'streaming'. "
            f"Check client.supports('streaming') before calling."
        )
