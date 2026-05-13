"""Unit tests for the `retrieval:` config block (feat-021 follow-up)."""

from __future__ import annotations

import pytest
from agentforge_core.config import (
    AgentForgeConfig,
    ModuleEntry,
    RerankerEntry,
    RetrievalConfig,
)
from pydantic import ValidationError


def test_retrieval_block_minimal_required_fields() -> None:
    """vector_store + embedder are required; everything else has defaults."""
    cfg = RetrievalConfig(
        vector_store=ModuleEntry(driver="sqlite", config={"path": "/tmp/v.db"}),
        embedder=ModuleEntry(driver="bedrock", config={"model": "titan"}),
    )
    assert cfg.reranker is None
    assert cfg.top_k == 5
    assert cfg.over_fetch_factor == 3
    assert cfg.batch_size == 32


def test_retrieval_block_full_round_trip() -> None:
    cfg = RetrievalConfig(
        vector_store=ModuleEntry(driver="postgres", config={}),
        embedder=ModuleEntry(driver="bedrock", config={}),
        reranker=RerankerEntry(name="sentence-transformers", config={"model": "x"}),
        top_k=10,
        over_fetch_factor=5,
        batch_size=64,
    )
    blob = cfg.model_dump_json()
    restored = RetrievalConfig.model_validate_json(blob)
    assert restored == cfg


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("top_k", 0),
        ("top_k", -1),
        ("over_fetch_factor", 0),
        ("batch_size", 0),
    ],
)
def test_retrieval_rejects_non_positive_knobs(field: str, bad_value: int) -> None:
    base = {
        "vector_store": ModuleEntry(driver="sqlite", config={}),
        "embedder": ModuleEntry(driver="bedrock", config={}),
        field: bad_value,
    }
    with pytest.raises(ValidationError):
        RetrievalConfig(**base)


def test_retrieval_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        RetrievalConfig(
            vector_store=ModuleEntry(driver="sqlite", config={}),
            embedder=ModuleEntry(driver="bedrock", config={}),
            unexpected_field=42,
        )


def test_reranker_entry_requires_name() -> None:
    with pytest.raises(ValidationError):
        RerankerEntry(name="")


def test_agentforge_config_retrieval_defaults_to_none() -> None:
    cfg = AgentForgeConfig()
    assert cfg.retrieval is None


def test_agentforge_config_accepts_full_retrieval_block() -> None:
    cfg = AgentForgeConfig(
        retrieval=RetrievalConfig(
            vector_store=ModuleEntry(driver="sqlite", config={"path": ":memory:"}),
            embedder=ModuleEntry(driver="bedrock", config={"model": "titan-v2"}),
            reranker=RerankerEntry(name="sentence-transformers", config={}),
            over_fetch_factor=4,
        ),
    )
    assert cfg.retrieval is not None
    assert cfg.retrieval.reranker is not None
    assert cfg.retrieval.reranker.name == "sentence-transformers"
    assert cfg.retrieval.over_fetch_factor == 4
