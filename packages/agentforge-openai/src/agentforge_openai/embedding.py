"""`OpenAIEmbeddingClient` — `EmbeddingClient` over OpenAI's
`embeddings.create()` API.

Supports `text-embedding-3-small` (1536 dims), `text-embedding-3-large`
(3072 dims), and the legacy `text-embedding-ada-002` (1536 dims).
The `text-embedding-3-*` models support Matryoshka-style truncation
via the `dimensions=` API parameter; declaring that capability lets
callers ask for a shorter vector at construction time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import register_embedding_provider
from agentforge_core.values.messages import EmbeddingResponse, TokenUsage

from agentforge_openai._pricing import embedding_cost_usd

if TYPE_CHECKING:
    from agentforge_openai._runner import OpenAIRunner


_PROVIDER_NAME = "openai"
_DEFAULT_TIMEOUT_SECONDS = 30.0

_MODEL_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_MATRYOSHKA_MODELS = frozenset({"text-embedding-3-small", "text-embedding-3-large"})


@register_embedding_provider("openai")
class OpenAIEmbeddingClient(EmbeddingClient):
    """`EmbeddingClient` over OpenAI's embeddings API."""

    def __init__(
        self,
        *,
        runner: OpenAIRunner,
        model: str,
        dimensions: int | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not model:
            raise ValueError("model must be a non-empty string")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        native = _MODEL_DIMS.get(model)
        if dimensions is not None:
            if dimensions < 1:
                raise ValueError("dimensions must be >= 1")
            if native is not None and dimensions > native:
                raise ValueError(
                    f"dimensions={dimensions} exceeds native={native} for {model}",
                )
            if dimensions != native and model not in _MATRYOSHKA_MODELS:
                raise ValueError(
                    f"{model} does not support dimension override (Matryoshka)",
                )
        self._runner = runner
        self._model = model
        self._dimensions = dimensions if dimensions is not None else native or 1536
        self._dim_arg: int | None = dimensions if dimensions != native else None
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_config(
        cls,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        dimensions: int | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> OpenAIEmbeddingClient:  # pragma: no cover — exercised only with `-m live`.
        runner = _build_sdk_runner(
            api_key=api_key,
            base_url=base_url,
            organization=organization,
        )
        return cls(
            runner=runner,
            model=model,
            dimensions=dimensions,
            timeout_seconds=timeout_seconds,
        )

    def dimensions(self) -> int:
        return self._dimensions

    def capabilities(self) -> set[str]:
        if self._model in _MATRYOSHKA_MODELS:
            return {"matryoshka"}
        return set()

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        if not texts:
            raise ValueError("texts must contain at least one item")
        raw = await self._runner.embeddings_create(
            model=self._model,
            inputs=texts,
            timeout_s=self._timeout_seconds,
            dimensions=self._dim_arg,
        )
        data = raw.get("data") or []
        vectors = tuple(tuple(float(v) for v in item.get("embedding") or []) for item in data)
        if any(len(v) != self._dimensions for v in vectors):
            raise ValueError(
                f"OpenAI returned vector with unexpected dimensionality; "
                f"expected {self._dimensions}, got "
                f"{[len(v) for v in vectors]}",
            )
        usage_raw = raw.get("usage") or {}
        usage = TokenUsage(
            input_tokens=int(usage_raw.get("prompt_tokens", 0)),
            output_tokens=0,
        )
        cost = embedding_cost_usd(self._model, input_tokens=usage.input_tokens)
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


def _build_sdk_runner(  # pragma: no cover — `-m live` only.
    *,
    api_key: str | None,
    base_url: str | None,
    organization: str | None,
) -> OpenAIRunner:
    try:
        import openai  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "openai is not installed. Install via "
            "`pip install agentforge-openai[openai]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from typing import Any  # noqa: PLC0415

    from agentforge_openai._runner import _OpenAISDKRunner  # noqa: PLC0415

    kwargs: dict[str, Any] = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    if organization:
        kwargs["organization"] = organization
    client = openai.AsyncOpenAI(**kwargs)
    return _OpenAISDKRunner(client)


__all__ = ["OpenAIEmbeddingClient"]
