"""In-memory `VoyageRunner` for unit tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class _EmbedCall:
    texts: list[str]
    model: str
    input_type: str | None
    output_dimension: int | None
    timeout_s: float


class FakeVoyageRunner:
    """In-memory recorder."""

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim
        self._tokens = 0
        self.embed_calls: list[_EmbedCall] = []
        self.closed = False

    def set_response_dim(self, dim: int) -> None:
        self._dim = dim

    def set_response_tokens(self, tokens: int) -> None:
        self._tokens = tokens

    async def embed(
        self,
        *,
        texts: list[str],
        model: str,
        input_type: str | None,
        output_dimension: int | None,
        timeout_s: float,
    ) -> dict[str, Any]:
        self.embed_calls.append(
            _EmbedCall(
                texts=list(texts),
                model=model,
                input_type=input_type,
                output_dimension=output_dimension,
                timeout_s=timeout_s,
            ),
        )
        dim = output_dimension or self._dim
        return {
            "embeddings": [[0.0] * dim for _ in texts],
            "total_tokens": self._tokens,
        }

    async def close(self) -> None:
        self.closed = True


__all__ = ["FakeVoyageRunner"]
