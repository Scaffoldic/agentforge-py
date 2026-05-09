"""Per-model price table loader and lookup.

Prices are shipped as `prices.json` next to this module. Loaded once
at first use and cached for the lifetime of the process. Cross-region
inference profile prefixes (`us.`, `eu.`, `apac.`, `global.`) are
stripped before lookup so a single row covers every routing flavour.

Updates to prices don't require a code release — just edit
`prices.json`. (A future feat could pull from the Pricing API; for
v0.1 a static table is honest about what the framework knows.)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from importlib import resources
from typing import Final

log = logging.getLogger(__name__)

# Cross-region inference profile prefixes (per AWS docs). When AWS
# adds a new geography, append the prefix here and the lookup
# transparently picks it up.
_CROSS_REGION_PREFIXES: Final[tuple[str, ...]] = ("us.", "eu.", "apac.", "global.")


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """Per-1k-token price for one Bedrock model.

    `output_per_1k` is `None` for embedding models (no output tokens).
    `dimensions` is the embedding dimensionality for embedding models;
    `None` otherwise.
    """

    input_per_1k: float
    output_per_1k: float | None = None
    dimensions: int | None = None


_TABLE: dict[str, ModelPrice] | None = None


def _load() -> dict[str, ModelPrice]:
    """Load and cache the price table. Idempotent; thread-safe enough
    for first-call races (worst case: a few duplicate parses)."""
    global _TABLE  # noqa: PLW0603 — module-level cache
    if _TABLE is not None:
        return _TABLE
    raw = resources.files(__package__).joinpath("prices.json").read_text("utf-8")
    parsed = json.loads(raw)
    table: dict[str, ModelPrice] = {}
    for model_id, row in parsed.get("models", {}).items():
        table[model_id] = ModelPrice(
            input_per_1k=float(row["input_per_1k"]),
            output_per_1k=(float(row["output_per_1k"]) if "output_per_1k" in row else None),
            dimensions=int(row["dimensions"]) if "dimensions" in row else None,
        )
    _TABLE = table
    return _TABLE


def strip_inference_prefix(model_id: str) -> str:
    """Strip `us.` / `eu.` / `apac.` / `global.` prefixes from a model id.

    Cross-region inference profiles route across destination regions
    but bill at the same per-token rate as the underlying model, so
    the table only needs the base id.
    """
    for prefix in _CROSS_REGION_PREFIXES:
        if model_id.startswith(prefix):
            return model_id[len(prefix) :]
    return model_id


def lookup(model_id: str) -> ModelPrice | None:
    """Return the price row for `model_id`, or `None` if unknown.

    Tries the raw id first (exact-match for region-pinned ids), then
    the prefix-stripped id (cross-region inference profile flavours).
    Returns `None` rather than raising — the caller (`compute_cost_usd`)
    decides how to handle unknown models. Logging the miss surfaces
    the gap during integration tests.
    """
    table = _load()
    if model_id in table:
        return table[model_id]
    base = strip_inference_prefix(model_id)
    if base != model_id and base in table:
        return table[base]
    return None


def compute_cost_usd(
    model_id: str,
    *,
    input_tokens: int,
    output_tokens: int = 0,
) -> float:
    """Compute USD cost from token usage for `model_id`.

    Returns `0.0` (with a logged warning, once per model) if the model
    is not in the price table — the caller still gets a usable
    `LLMResponse`; cost just shows as zero rather than crashing the
    run. Production users add the missing model to `prices.json`.
    """
    price = lookup(model_id)
    if price is None:
        _log_unknown_once(model_id)
        return 0.0
    cost = (input_tokens / 1000.0) * price.input_per_1k
    if output_tokens and price.output_per_1k is not None:
        cost += (output_tokens / 1000.0) * price.output_per_1k
    return cost


_warned_models: set[str] = set()


def _log_unknown_once(model_id: str) -> None:
    """Warn at most once per unknown model id to avoid log spam."""
    if model_id in _warned_models:
        return
    _warned_models.add(model_id)
    log.warning(
        "agentforge-bedrock: no price data for model %r; reporting cost_usd=0.0. "
        "Add an entry to prices.json to enable cost tracking.",
        model_id,
    )


def known_models() -> tuple[str, ...]:
    """Sorted list of known model ids — used by tests and diagnostics."""
    return tuple(sorted(_load().keys()))


def reset_cache() -> None:
    """Test-only: clear the cached table and the warned-models set."""
    global _TABLE  # noqa: PLW0603 — module-level cache
    _TABLE = None
    _warned_models.clear()
