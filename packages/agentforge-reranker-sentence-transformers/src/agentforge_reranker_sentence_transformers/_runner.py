"""CrossEncoder runner Protocol + production SDK wrapper."""

from __future__ import annotations

from typing import Any, Protocol


class CrossEncoderRunner(Protocol):
    """Lifecycle Protocol for the single SDK call we make.

    Mirrors `sentence_transformers.CrossEncoder.predict` exactly,
    enough for tests to inject a fake that returns scripted scores.
    """

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:  # pragma: no cover
        """Return one raw relevance score per ``(query, candidate_text)`` pair."""
        ...

    def close(self) -> None:  # pragma: no cover
        """Release model handles (no-op for SDK; tests may use this)."""
        ...


class _SentenceTransformersRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``sentence_transformers.CrossEncoder``."""

    def __init__(self, model: Any) -> None:
        self._model = model

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        # CrossEncoder.predict returns numpy.ndarray; convert to plain
        # python floats for downstream serialisation.
        raw = self._model.predict(pairs)
        return [float(x) for x in raw]

    def close(self) -> None:
        # sentence_transformers has no explicit close; the model is
        # garbage-collected when the reference drops.
        return None


__all__ = ["CrossEncoderRunner"]
