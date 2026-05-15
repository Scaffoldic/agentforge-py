"""Per-model price table for OpenAI models.

Prices are USD per 1M tokens, snapshotted 2026-05-14 from
OpenAI's public pricing page. Embedding models use the same
shape but only `input` is meaningful.

A model not in the table returns `0.0` and we log a debug
message — callers see `cost_usd=0.0` rather than crashing.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_CHAT_PRICES: dict[str, tuple[float, float]] = {
    # Each entry: input / output USD per 1M tokens.
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (3.0, 12.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "o3": (10.0, 40.0),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
}

_EMBED_PRICES: dict[str, float] = {
    # Each entry: USD per 1M input tokens (embeddings have no output).
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
}


def chat_cost_usd(model: str, *, input_tokens: int, output_tokens: int) -> float:
    canonical = _canonical_chat(model)
    prices = _CHAT_PRICES.get(canonical)
    if prices is None:
        log.debug("agentforge-openai: no chat-price entry for %r; cost_usd=0.0", model)
        return 0.0
    in_p, out_p = prices
    return (input_tokens / 1_000_000) * in_p + (output_tokens / 1_000_000) * out_p


def embedding_cost_usd(model: str, *, input_tokens: int) -> float:
    price = _EMBED_PRICES.get(model)
    if price is None:
        log.debug("agentforge-openai: no embedding-price entry for %r; cost_usd=0.0", model)
        return 0.0
    return (input_tokens / 1_000_000) * price


def _canonical_chat(model: str) -> str:
    """Strip dated suffixes (`-2026-03-01`, `-20260301`) for lookup."""
    # OpenAI uses `-YYYY-MM-DD` style suffixes; chop after the model
    # family if a date-like tail is present.
    for suffix_prefix in ("-2025", "-2026", "-2027", "-2028", "-2029", "-2030"):
        idx = model.find(suffix_prefix)
        if idx > 0:
            return model[:idx]
    return model


__all__ = ["chat_cost_usd", "embedding_cost_usd"]
