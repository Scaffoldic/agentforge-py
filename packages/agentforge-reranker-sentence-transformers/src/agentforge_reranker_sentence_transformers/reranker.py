"""`SentenceTransformersReranker` — cross-encoder reranker.

Implements the locked `Reranker` ABC from feat-021 against
``sentence_transformers.CrossEncoder.predict``. Applies a sigmoid
to the raw logits so returned scores satisfy the
``VectorMatch.score ∈ [0, 1]`` contract.

Construction is two paths:

- ``SentenceTransformersReranker(runner=<CrossEncoderRunner>)`` —
  direct injection (tests).
- ``SentenceTransformersReranker.from_config(model=...)`` — builds
  the production runner by lazy-importing ``sentence_transformers``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from agentforge_core.contracts.reranker import Reranker
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.vector import VectorMatch

if TYPE_CHECKING:
    from agentforge_reranker_sentence_transformers._runner import CrossEncoderRunner


_DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _sigmoid(x: float) -> float:
    """Logistic sigmoid mapping (-∞, +∞) → (0, 1).

    Numerically-stable variant: routes through the larger branch
    so very negative logits don't blow up ``math.exp``.
    """
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


class SentenceTransformersReranker(Reranker):
    """Cross-encoder reranker backed by ``sentence-transformers``.

    Args:
        runner: A `CrossEncoderRunner` (test fake or production
            SDK wrapper). The reranker is the only place we touch
            the runner.
    """

    def __init__(self, *, runner: CrossEncoderRunner) -> None:
        self._runner = runner

    @classmethod
    def from_config(
        cls,
        *,
        model: str = _DEFAULT_MODEL,
    ) -> SentenceTransformersReranker:  # pragma: no cover — `-m live` only.
        """Build a reranker backed by a real `CrossEncoder` model."""
        runner = _build_cross_encoder_runner(model=model)
        return cls(runner=runner)

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

        pairs = [(query, c.text) for c in candidates]
        raw_scores = self._runner.predict(pairs)
        if len(raw_scores) != len(candidates):
            msg = f"CrossEncoder returned {len(raw_scores)} scores for {len(candidates)} pairs"
            raise RuntimeError(msg)

        rescored = [
            VectorMatch(
                id=c.id,
                text=c.text,
                metadata=c.metadata,
                score=_sigmoid(float(s)),
            )
            for c, s in zip(candidates, raw_scores, strict=True)
        ]
        rescored.sort(key=lambda m: m.score, reverse=True)
        if top_k is not None:
            return rescored[:top_k]
        return rescored

    async def close(self) -> None:
        self._runner.close()

    def capabilities(self) -> set[str]:
        return {"local", "batched"}


def _build_cross_encoder_runner(*, model: str) -> CrossEncoderRunner:  # pragma: no cover
    """Lazy-import `sentence_transformers` and build the production runner."""
    try:
        from sentence_transformers import CrossEncoder  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "sentence-transformers is not installed. Install via "
            "`pip install agentforge-reranker-sentence-transformers"
            "[sentence-transformers]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_reranker_sentence_transformers._runner import (  # noqa: PLC0415
        _SentenceTransformersRunner,
    )

    return _SentenceTransformersRunner(CrossEncoder(model))


__all__ = ["SentenceTransformersReranker"]
