"""`VoyageEmbeddingClient` — `EmbeddingClient` over Voyage AI.

Voyage's embedding API supports input-type optimisation
(`query` vs `document`) and Matryoshka truncation
(`output_dimension`) for selected models.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import register_embedding_provider
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage

if TYPE_CHECKING:
    from agentforge_voyage._runner import VoyageRunner


log = logging.getLogger(__name__)

_PROVIDER_NAME = "voyage"
_DEFAULT_TIMEOUT_SECONDS = 30.0

_MODEL_INFO: dict[str, tuple[int, bool, bool]] = {
    # Each entry: (native_dim, supports_matryoshka, multimodal).
    "voyage-3-large": (1024, True, False),
    "voyage-3": (1024, True, False),
    "voyage-3-lite": (512, False, False),
    "voyage-code-3": (1024, True, False),
    "voyage-finance-2": (1024, False, False),
    "voyage-law-2": (1024, False, False),
    "voyage-multimodal-3": (1024, False, True),
}

# Per-million-token USD prices snapshotted 2026-05-14.
_PRICES: dict[str, float] = {
    "voyage-3-large": 0.18,
    "voyage-3": 0.06,
    "voyage-3-lite": 0.02,
    "voyage-code-3": 0.18,
    "voyage-finance-2": 0.12,
    "voyage-law-2": 0.12,
    "voyage-multimodal-3": 0.18,
}


@register_embedding_provider("voyage")
class VoyageEmbeddingClient(EmbeddingClient):
    """`EmbeddingClient` over Voyage AI."""

    def __init__(
        self,
        *,
        runner: VoyageRunner,
        model: str,
        dimensions: int | None = None,
        input_type: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not model:
            raise ValueError("model must be a non-empty string")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if input_type is not None and input_type not in {"query", "document"}:
            raise ValueError("input_type must be 'query', 'document', or None")
        info = _MODEL_INFO.get(model)
        native_dim = info[0] if info else 1024
        if dimensions is not None:
            if dimensions < 1:
                raise ValueError("dimensions must be >= 1")
            if info is not None:
                if dimensions > native_dim:
                    raise ValueError(
                        f"dimensions={dimensions} exceeds native={native_dim} for {model}",
                    )
                if dimensions != native_dim and not info[1]:
                    raise ValueError(f"{model} does not support dimension override")
        self._runner = runner
        self._model = model
        self._dimensions = dimensions or native_dim
        self._dim_arg: int | None = dimensions if dimensions != native_dim else None
        self._input_type = input_type
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_config(
        cls,
        *,
        model: str,
        api_key: str | None = None,
        dimensions: int | None = None,
        input_type: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> VoyageEmbeddingClient:  # pragma: no cover — `-m live` only.
        runner = _build_sdk_runner(api_key=api_key)
        return cls(
            runner=runner,
            model=model,
            dimensions=dimensions,
            input_type=input_type,
            timeout_seconds=timeout_seconds,
        )

    def dimensions(self) -> int:
        return self._dimensions

    def capabilities(self) -> set[str]:
        info = _MODEL_INFO.get(self._model)
        caps: set[str] = set()
        if info and info[1]:
            caps.add("matryoshka")
        if info and info[2]:
            caps.add("multimodal")
        return caps

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        if not texts:
            raise ValueError("texts must contain at least one item")
        raw = await self._runner.embed(
            texts=texts,
            model=self._model,
            input_type=self._input_type,
            output_dimension=self._dim_arg,
            timeout_s=self._timeout_seconds,
        )
        embeddings_raw = raw.get("embeddings") or []
        vectors = tuple(tuple(float(v) for v in emb) for emb in embeddings_raw)
        if any(len(v) != self._dimensions for v in vectors):
            raise ValueError(
                f"Voyage returned vector with unexpected dimensionality; "
                f"expected {self._dimensions}, got {[len(v) for v in vectors]}",
            )
        tokens = int(raw.get("total_tokens", 0) or 0)
        usage = TokenUsage(input_tokens=tokens, output_tokens=0)
        price = _PRICES.get(self._model, 0.0)
        cost = (tokens / 1_000_000) * price
        return EmbeddingResponse(
            vectors=vectors,
            dimensions=self._dimensions,
            usage=usage,
            cost_usd=cost,
            model=self._model,
            provider=_PROVIDER_NAME,
        )

    async def close(self) -> None:
        await self._runner.close()


def _build_sdk_runner(*, api_key: str | None) -> VoyageRunner:  # pragma: no cover — `-m live` only.
    try:
        import voyageai  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "voyageai is not installed. Install via "
            "`pip install agentforge-voyage[voyage]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_voyage._runner import _VoyageSDKRunner  # noqa: PLC0415

    client = voyageai.AsyncClient(api_key=api_key) if api_key else voyageai.AsyncClient()
    return _VoyageSDKRunner(client)


__all__ = ["VoyageEmbeddingClient"]
