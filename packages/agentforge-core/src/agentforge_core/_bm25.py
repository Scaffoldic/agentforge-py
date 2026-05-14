"""Private pure-Python BM25 helper (feat-022).

Used by ``VectorStore`` drivers that don't have a native lexical
path (e.g. the in-memory store) and by future hybrid retrieval
test fixtures. Public-facing hybrid retrieval is driven via
``Retriever(mode="hybrid")`` — this module is an implementation
detail and not part of the framework's stable API.

Tokeniser: lowercase + ``\\W+`` split + drop tokens of length ≤ 1.
No stemming / stopword removal in v0.2 (keeps the dependency
surface zero). Defaults follow Robertson: ``k1=1.5`` and ``b=0.75``.

Formula (Okapi BM25):

    score(D, Q) = Σ_t∈Q IDF(t) · TF_norm(t, D)

    IDF(t) = ln( (N - df(t) + 0.5) / (df(t) + 0.5) + 1 )

    TF_norm(t, D) =
        ( tf(t, D) · (k1 + 1) ) /
        ( tf(t, D) + k1 · (1 - b + b · |D| / avg_dl) )
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Final

_TOKEN_RE: Final = re.compile(r"\W+", re.UNICODE)
_MIN_TOKEN_LEN: Final = 2


def _tokenise(text: str) -> list[str]:
    """Lowercase, split on non-word characters, drop tokens ≤ 1 char."""
    return [tok for tok in _TOKEN_RE.split(text.lower()) if len(tok) >= _MIN_TOKEN_LEN]


class _BM25Index:
    """In-memory BM25 index over ``(doc_id, text)`` pairs.

    Maintains per-document term frequencies, document lengths, and a
    global document frequency table. Designed for small corpora
    (~thousands of docs) — every ``add`` / ``delete`` is O(|tokens|)
    and ``score`` is O(|query tokens| · |matching docs|).

    Not thread-safe. Callers wrap with a mutex if needed.
    """

    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        if k1 < 0:
            raise ValueError(f"k1 must be >= 0, got {k1}")
        if not 0.0 <= b <= 1.0:
            raise ValueError(f"b must be in [0, 1], got {b}")
        self._k1 = k1
        self._b = b
        self._tf: dict[str, Counter[str]] = {}
        self._doc_len: dict[str, int] = {}
        self._df: Counter[str] = Counter()

    def add(self, doc_id: str, text: str) -> None:
        """Insert or replace the document at ``doc_id``."""
        if doc_id in self._tf:
            self.delete(doc_id)
        tokens = _tokenise(text)
        if not tokens:
            self._tf[doc_id] = Counter()
            self._doc_len[doc_id] = 0
            return
        tf = Counter(tokens)
        self._tf[doc_id] = tf
        self._doc_len[doc_id] = len(tokens)
        for term in tf:
            self._df[term] += 1

    def delete(self, doc_id: str) -> bool:
        """Remove the document. Returns True if it existed."""
        tf = self._tf.pop(doc_id, None)
        if tf is None:
            return False
        self._doc_len.pop(doc_id, None)
        for term in tf:
            self._df[term] -= 1
            if self._df[term] <= 0:
                del self._df[term]
        return True

    def __len__(self) -> int:
        return len(self._tf)

    def score(self, query: str, *, limit: int) -> list[tuple[str, float]]:
        """Return up to ``limit`` ``(doc_id, score)`` pairs sorted desc.

        Scores are raw BM25 (unbounded ≥ 0). Empty corpus or empty
        query returns ``[]``. Callers that want normalised scores
        divide by the top score.
        """
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        query_tokens = _tokenise(query)
        if not query_tokens or not self._tf:
            return []

        n_docs = len(self._tf)
        total_len = sum(self._doc_len.values())
        avg_dl = total_len / n_docs if n_docs else 0.0

        idf_cache: dict[str, float] = {}
        for term in set(query_tokens):
            df = self._df.get(term, 0)
            # +1 inside the log keeps IDF non-negative even when
            # df > N/2 (which can happen on tiny corpora).
            idf_cache[term] = math.log(((n_docs - df + 0.5) / (df + 0.5)) + 1.0)

        scored: list[tuple[str, float]] = []
        for doc_id, tf in self._tf.items():
            doc_len = self._doc_len[doc_id]
            score = 0.0
            for term in query_tokens:
                tf_term = tf.get(term, 0)
                if tf_term == 0:
                    continue
                denom = tf_term + self._k1 * (
                    1.0 - self._b + self._b * (doc_len / avg_dl if avg_dl else 0.0)
                )
                score += idf_cache[term] * (tf_term * (self._k1 + 1.0)) / denom
            if score > 0.0:
                scored.append((doc_id, score))

        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:limit]
