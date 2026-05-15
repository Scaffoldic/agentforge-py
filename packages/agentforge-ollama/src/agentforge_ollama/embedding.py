"""`OllamaEmbeddingClient` — `EmbeddingClient` over Ollama's `/api/embed`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import register_embedding_provider
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage

if TYPE_CHECKING:
    from agentforge_ollama._runner import OllamaRunner


_PROVIDER_NAME = "ollama"
_DEFAULT_TIMEOUT_SECONDS = 60.0


@register_embedding_provider("ollama")
class OllamaEmbeddingClient(EmbeddingClient):
    """`EmbeddingClient` over Ollama's local embedding endpoint."""

    def __init__(
        self,
        *,
        runner: OllamaRunner,
        model: str,
        dimensions: int,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not model:
            raise ValueError("model must be a non-empty string")
        if dimensions < 1:
            raise ValueError("dimensions must be >= 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._runner = runner
        self._model = model
        self._dimensions = dimensions
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_config(
        cls,
        *,
        model: str,
        dimensions: int,
        host: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> OllamaEmbeddingClient:  # pragma: no cover — `-m live` only.
        runner = _build_sdk_runner(host=host)
        return cls(
            runner=runner,
            model=model,
            dimensions=dimensions,
            timeout_seconds=timeout_seconds,
        )

    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        if not texts:
            raise ValueError("texts must contain at least one item")
        raw = await self._runner.embed(
            model=self._model,
            inputs=texts,
            timeout_s=self._timeout_seconds,
        )
        embeddings_raw = raw.get("embeddings") or []
        vectors = tuple(tuple(float(v) for v in emb) for emb in embeddings_raw)
        if any(len(v) != self._dimensions for v in vectors):
            raise ValueError(
                f"Ollama returned vector with unexpected dimensionality; "
                f"expected {self._dimensions}, got {[len(v) for v in vectors]}",
            )
        tokens = int(raw.get("prompt_eval_count", 0) or 0)
        return EmbeddingResponse(
            vectors=vectors,
            dimensions=self._dimensions,
            usage=TokenUsage(input_tokens=tokens, output_tokens=0),
            cost_usd=0.0,  # local inference.
            model=self._model,
            provider=_PROVIDER_NAME,
        )

    async def close(self) -> None:
        await self._runner.close()


def _build_sdk_runner(*, host: str | None) -> OllamaRunner:  # pragma: no cover — `-m live` only.
    try:
        import ollama  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "ollama is not installed. Install via "
            "`pip install agentforge-ollama[ollama]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_ollama._runner import _OllamaSDKRunner  # noqa: PLC0415

    client = ollama.AsyncClient(host=host) if host else ollama.AsyncClient()
    return _OllamaSDKRunner(client)


__all__ = ["OllamaEmbeddingClient"]
