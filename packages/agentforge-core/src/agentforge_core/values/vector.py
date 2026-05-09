"""Frozen value types for the `VectorStore` contract.

`VectorItem` is what callers upsert into a vector store; `VectorMatch`
is what searches return. Both are immutable Pydantic models so they
can be freely passed across async boundaries without aliasing bugs.

Per ADR-0007 these shapes are part of the framework's locked surface.
Adding a field is a minor bump; removing or renaming requires a major
bump.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VectorItem(BaseModel):
    """One indexable record in a `VectorStore`.

    Attributes:
        id: Caller-controlled identifier. Re-upserting an existing id
            replaces the prior record (write-through, not append).
        vector: The embedding. Length must match the store's declared
            `dimensions()`; mismatch raises on `upsert`.
        text: The source text the vector was computed from. Surfaced on
            `VectorMatch` so callers don't have to keep a parallel
            text store. Empty strings are allowed but discouraged.
        metadata: Free-form key-value tags. Used by `search`'s
            `filter_metadata=` argument for AND-style filtering. Kept
            as a plain dict (not frozen) so Pydantic doesn't have to
            recurse into arbitrary user payloads.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    id: str = Field(min_length=1)
    vector: tuple[float, ...]
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorMatch(BaseModel):
    """One result from `VectorStore.search`.

    `score` is normalised cosine similarity in `[0, 1]`:
      - 1.0 means identical direction (highest relevance)
      - 0.0 means orthogonal (effectively unrelated)
      - the contract is store-agnostic; drivers that return raw cosine
        distance or negative inner-product convert at the boundary.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float = Field(ge=0.0, le=1.0)
