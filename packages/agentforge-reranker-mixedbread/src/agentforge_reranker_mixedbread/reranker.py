"""`MixedbreadReranker` — Mixedbread AI managed-API reranker.

Implements the locked `Reranker` ABC from feat-021 against
Mixedbread's Rerank API. Scores from the API are already in
``[0, 1]``; the reranker applies a defensive clamp.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentforge_core.contracts.reranker import Reranker
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.vector import VectorMatch

if TYPE_CHECKING:
    from agentforge_reranker_mixedbread._runner import MixedbreadRunner


_DEFAULT_MODEL = "mixedbread-ai/mxbai-rerank-large-v1"
_DEFAULT_TIMEOUT_S = 30.0


def _clamp_unit(score: float) -> float:
    return max(0.0, min(1.0, score))


class MixedbreadReranker(Reranker):
    """Mixedbread-backed managed-API reranker."""

    def __init__(self, *, runner: MixedbreadRunner, model: str = _DEFAULT_MODEL) -> None:
        self._runner = runner
        self._model = model

    @classmethod
    def from_config(
        cls,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> MixedbreadReranker:  # pragma: no cover — exercised only with `-m live`.
        runner = _build_mixedbread_runner(api_key=api_key, timeout_s=timeout_s)
        return cls(runner=runner, model=model)

    @property
    def model(self) -> str:
        return self._model

    async def rerank(
        self,
        query: str,
        candidates: list[VectorMatch],
        *,
        top_k: int | None = None,
    ) -> list[VectorMatch]:
        if top_k is not None and top_k < 1:
            msg = f"top_k must be >= 1, got {top_k}"
            raise ValueError(msg)
        if not candidates:
            return []

        n = len(candidates)
        request_top_k = top_k if top_k is not None else n

        documents = [c.text for c in candidates]
        scored = self._runner.rerank(
            query=query,
            documents=documents,
            model=self._model,
            top_k=request_top_k,
        )

        return [
            VectorMatch(
                id=candidates[idx].id,
                text=candidates[idx].text,
                metadata=candidates[idx].metadata,
                score=_clamp_unit(score),
            )
            for idx, score in scored
        ]

    async def close(self) -> None:
        self._runner.close()

    def capabilities(self) -> set[str]:
        return {"managed", "batched"}


def _build_mixedbread_runner(  # pragma: no cover — `-m live` only.
    *,
    api_key: str,
    timeout_s: float,
) -> MixedbreadRunner:
    """Lazy-import `mixedbread_ai` and build the production runner."""
    try:
        from mixedbread_ai.client import MixedbreadAI  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "mixedbread-ai is not installed. Install via "
            "`pip install agentforge-reranker-mixedbread[mixedbread]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_reranker_mixedbread._runner import _MixedbreadClientRunner  # noqa: PLC0415

    client = MixedbreadAI(api_key=api_key)
    return _MixedbreadClientRunner(client, timeout_s=timeout_s)


__all__ = ["MixedbreadReranker"]
