"""`VoyageReranker` — Voyage AI managed-API reranker.

Implements the locked `Reranker` ABC from feat-021 against
the Voyage Rerank API. Scores returned by the Voyage API are
already in ``[0, 1]``; the reranker applies a defensive clamp.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentforge_core.contracts.reranker import Reranker
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.vector import VectorMatch

if TYPE_CHECKING:
    from agentforge_reranker_voyage._runner import VoyageRunner


_DEFAULT_MODEL = "rerank-2"
_DEFAULT_TIMEOUT_S = 30.0


def _clamp_unit(score: float) -> float:
    return max(0.0, min(1.0, score))


class VoyageReranker(Reranker):
    """Voyage-backed managed-API reranker."""

    def __init__(self, *, runner: VoyageRunner, model: str = _DEFAULT_MODEL) -> None:
        self._runner = runner
        self._model = model

    @classmethod
    def from_config(
        cls,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> VoyageReranker:  # pragma: no cover — exercised only with `-m live`.
        runner = _build_voyage_runner(api_key=api_key, timeout_s=timeout_s)
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


def _build_voyage_runner(  # pragma: no cover — `-m live` only.
    *,
    api_key: str,
    timeout_s: float,
) -> VoyageRunner:
    """Lazy-import `voyageai` and build the production runner."""
    try:
        import voyageai  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "voyageai is not installed. Install via "
            "`pip install agentforge-reranker-voyage[voyage]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_reranker_voyage._runner import _VoyageClientRunner  # noqa: PLC0415

    client = voyageai.Client(api_key=api_key)
    return _VoyageClientRunner(client, timeout_s=timeout_s)


__all__ = ["VoyageReranker"]
