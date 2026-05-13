"""In-memory `CrossEncoderRunner` for unit tests + downstream integration.

Records every ``predict`` call's pair list and returns scripted
raw-logit scores. Tests use ``set_scores`` to control what the
reranker sees.
"""

from __future__ import annotations


class FakeCrossEncoderRunner:
    """In-memory recorder of every predict call + scripted scoring."""

    def __init__(self, scores: list[float] | None = None) -> None:
        self._scores = list(scores or [])
        self.predict_calls: list[list[tuple[str, str]]] = []
        self.closed = False

    def set_scores(self, scores: list[float]) -> None:
        """Replace the scripted score list. Returned in order on
        subsequent ``predict`` calls."""
        self._scores = list(scores)

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        self.predict_calls.append(list(pairs))
        if not pairs:
            return []
        if len(self._scores) < len(pairs):
            msg = (
                f"FakeCrossEncoderRunner: scripted {len(self._scores)} scores "
                f"but called with {len(pairs)} pairs"
            )
            raise ValueError(msg)
        return self._scores[: len(pairs)]

    def close(self) -> None:
        self.closed = True


__all__ = ["FakeCrossEncoderRunner"]
