"""`CohereReranker` — Cohere managed-API reranker.

Implements the locked `Reranker` ABC from feat-021 against
the Cohere Rerank API. Scores returned by the Cohere API are
already normalised to ``[0, 1]``; we apply a defensive clamp
in case of edge cases.

Construction:

- ``CohereReranker(runner=<CohereRunner>)`` — direct
  injection (tests).
- ``CohereReranker.from_config(api_key=..., model=...,
  timeout_s=30.0)`` — builds the production runner by
  lazy-importing ``cohere``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentforge_core.contracts.reranker import Reranker
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.vector import VectorMatch

if TYPE_CHECKING:
    from agentforge_reranker_cohere._runner import CohereRunner


_DEFAULT_MODEL = "rerank-english-v3.0"
_DEFAULT_TIMEOUT_S = 30.0


def _clamp_unit(score: float) -> float:
    """Defensive clamp into ``[0, 1]`` to satisfy
    `VectorMatch.score` constraints."""
    return max(0.0, min(1.0, score))


class CohereReranker(Reranker):
    """Cohere-backed managed-API reranker."""

    def __init__(self, *, runner: CohereRunner, model: str = _DEFAULT_MODEL) -> None:
        self._runner = runner
        self._model = model

    @classmethod
    def from_config(
        cls,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> CohereReranker:  # pragma: no cover — exercised only with `-m live`.
        """Build a `CohereReranker` backed by a real `cohere.Client`."""
        runner = _build_cohere_runner(api_key=api_key, timeout_s=timeout_s)
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

        # Cohere caps the response server-side via `top_n`. When the
        # caller wants every candidate re-scored, pass the full count.
        n = len(candidates)
        request_top_n = top_k if top_k is not None else n

        documents = [c.text for c in candidates]
        scored = self._runner.rerank(
            query=query,
            documents=documents,
            model=self._model,
            top_n=request_top_n,
        )

        # Cohere returns results already sorted desc by score.
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


def _build_cohere_runner(  # pragma: no cover — `-m live` only.
    *,
    api_key: str,
    timeout_s: float,
) -> CohereRunner:
    """Lazy-import `cohere` and build the production runner."""
    try:
        import cohere  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "cohere is not installed. Install via "
            "`pip install agentforge-reranker-cohere[cohere]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_reranker_cohere._runner import _CohereClientRunner  # noqa: PLC0415

    client = cohere.Client(api_key=api_key)
    return _CohereClientRunner(client, timeout_s=timeout_s)


__all__ = ["CohereReranker"]
