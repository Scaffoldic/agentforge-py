"""Per-model price table for Anthropic native models.

Prices are USD per 1M tokens, snapshotted 2026-05-14 from
Anthropic's public pricing page. Cache-read tokens are billed at
10% of input-token rate; cache-write tokens at 125%.

A model not in the table returns `(0.0, 0.0, 0.0, 0.0)` and we
log a debug message — callers see `cost_usd=0.0` rather than
crashing. Adding a new model is a one-line entry.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_DATE_SUFFIX_PARTS = 2
_DATE_SUFFIX_LEN = 8

# Each entry: input / output / cache-read / cache-write USD per 1M tokens.
_PRICES: dict[str, tuple[float, float, float, float]] = {
    # Claude Sonnet 4.7 (cutoff 2026-01)
    "claude-sonnet-4-7": (3.0, 15.0, 0.30, 3.75),
    "claude-sonnet-4-7-1m": (3.0, 15.0, 0.30, 3.75),
    # Claude Opus 4.7
    "claude-opus-4-7": (15.0, 75.0, 1.50, 18.75),
    # Claude Haiku 4.5
    "claude-haiku-4-5": (0.80, 4.0, 0.08, 1.0),
    # 4.x line (carryover)
    "claude-sonnet-4-6": (3.0, 15.0, 0.30, 3.75),
    "claude-opus-4-6": (15.0, 75.0, 1.50, 18.75),
}


def compute_cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Estimate USD cost from token counts using the snapshot table."""
    # Strip dated suffixes (e.g. `-20260301`) so dated model strings
    # match the canonical entry.
    canonical = _canonical_model(model)
    prices = _PRICES.get(canonical)
    if prices is None:
        log.debug("agentforge-anthropic: no price entry for model %r; cost_usd=0.0", model)
        return 0.0
    in_p, out_p, cache_r_p, cache_w_p = prices
    return (
        (input_tokens / 1_000_000) * in_p
        + (output_tokens / 1_000_000) * out_p
        + (cache_read_tokens / 1_000_000) * cache_r_p
        + (cache_write_tokens / 1_000_000) * cache_w_p
    )


def _canonical_model(model: str) -> str:
    """Strip dated / region suffixes for price-table lookup."""
    # Anthropic dated suffixes look like `-20260301`; remove the
    # trailing `-<8-digit>` chunk if present.
    parts = model.rsplit("-", 1)
    if (
        len(parts) == _DATE_SUFFIX_PARTS
        and parts[1].isdigit()
        and len(parts[1]) == _DATE_SUFFIX_LEN
    ):
        return parts[0]
    return model


__all__ = ["compute_cost_usd"]
