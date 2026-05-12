"""Provider-aware tokenisers for `TokenBudget` (feat-020 v0.2).

The default `TokenBudget` ships a 4-chars-per-token heuristic
that works for English-ish prose but drifts widely on code +
non-ASCII content. For accurate budget enforcement, supply a
`Tokeniser`: any callable that maps a string to a token count.

Two built-ins:

- :func:`tiktoken_tokeniser` — counts via the
  `tiktoken` library used by OpenAI-compatible models.
- :func:`anthropic_tokeniser` — counts via the Anthropic
  SDK's `count_tokens` API.

Both lazy-import their backing SDKs and raise :class:`ModuleError`
with pip remediation when the SDK isn't installed. Users
provide their own callable when they want a different
tokeniser.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Any, cast

from agentforge_core.production.exceptions import ModuleError

Tokeniser = Callable[[str], int]
"""Map an input string to a non-negative integer token count."""


@lru_cache(maxsize=8)
def _load_tiktoken_encoding(model: str) -> Any:  # pragma: no cover — exercised via build
    try:
        import tiktoken  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "tiktoken is not installed. Install via "
            "`pip install tiktoken` to use tiktoken_tokeniser."
        )
        raise ModuleError(msg) from exc
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def tiktoken_tokeniser(model: str = "gpt-4o-mini") -> Tokeniser:
    """Build a tiktoken-backed `Tokeniser` for ``model``.

    Falls back to the ``cl100k_base`` encoding when the model
    name isn't in tiktoken's registry.
    """
    enc = _load_tiktoken_encoding(model)

    def _count(text: str) -> int:
        return len(enc.encode(text))

    return _count


def anthropic_tokeniser() -> Tokeniser:  # pragma: no cover — exercised via build
    """Build an Anthropic-SDK-backed `Tokeniser`.

    Uses the synchronous `count_tokens(text)` method on a
    process-wide Anthropic client. Suitable for offline token
    counting where no API key is needed.
    """
    try:
        import anthropic  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "anthropic SDK is not installed. Install via "
            "`pip install anthropic` to use anthropic_tokeniser."
        )
        raise ModuleError(msg) from exc

    client = anthropic.Anthropic()

    def _count(text: str) -> int:
        return int(cast("Any", client).count_tokens(text))

    return _count


__all__ = [
    "Tokeniser",
    "anthropic_tokeniser",
    "tiktoken_tokeniser",
]
