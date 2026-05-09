"""Unit tests for the Bedrock price lookup."""

from __future__ import annotations

import logging

import pytest
from agentforge_bedrock._pricing import (
    compute_cost_usd,
    known_models,
    lookup,
    reset_cache,
    strip_inference_prefix,
)


@pytest.fixture(autouse=True)
def _reset_pricing_cache() -> None:
    reset_cache()


def test_strip_inference_prefix_handles_each_geo() -> None:
    base = "anthropic.claude-3-haiku-20240307-v1:0"
    assert strip_inference_prefix(f"us.{base}") == base
    assert strip_inference_prefix(f"eu.{base}") == base
    assert strip_inference_prefix(f"apac.{base}") == base
    assert strip_inference_prefix(f"global.{base}") == base


def test_strip_inference_prefix_passes_unprefixed_unchanged() -> None:
    base = "anthropic.claude-3-haiku-20240307-v1:0"
    assert strip_inference_prefix(base) == base


def test_lookup_finds_known_model() -> None:
    price = lookup("anthropic.claude-3-haiku-20240307-v1:0")
    assert price is not None
    assert price.input_per_1k > 0
    assert price.output_per_1k is not None


def test_lookup_finds_cross_region_via_prefix_strip() -> None:
    price = lookup("us.anthropic.claude-3-haiku-20240307-v1:0")
    assert price is not None


def test_lookup_returns_none_for_unknown_model() -> None:
    assert lookup("not-a-real-model") is None


def test_compute_cost_unknown_model_logs_once_and_returns_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        c1 = compute_cost_usd("unknown-model-x", input_tokens=1000)
        c2 = compute_cost_usd("unknown-model-x", input_tokens=2000)
    assert c1 == 0.0
    assert c2 == 0.0
    # Only one warning across both calls.
    warns = [r for r in caplog.records if "unknown-model-x" in r.message]
    assert len(warns) == 1


def test_compute_cost_uses_input_and_output_rates() -> None:
    cost = compute_cost_usd(
        "anthropic.claude-3-haiku-20240307-v1:0",
        input_tokens=1000,
        output_tokens=1000,
    )
    # Haiku is $0.00025 in + $0.00125 out per 1k → $0.0015 total.
    assert cost == pytest.approx(0.0015, rel=1e-6)


def test_compute_cost_handles_embedding_model_without_output_rate() -> None:
    """Embedding rows have no `output_per_1k`; passing output_tokens
    is harmless and only the input rate applies."""
    cost = compute_cost_usd(
        "amazon.titan-embed-text-v2:0",
        input_tokens=1000,
        output_tokens=999,  # ignored
    )
    # Titan v2 = $0.00002 per 1k input
    assert cost == pytest.approx(0.00002, rel=1e-6)


def test_known_models_includes_anthropic_and_embedding_families() -> None:
    models = known_models()
    assert any("anthropic" in m for m in models)
    assert any("titan" in m for m in models)
    assert any("cohere" in m for m in models)


def test_compute_cost_zero_tokens_is_zero() -> None:
    cost = compute_cost_usd(
        "anthropic.claude-3-haiku-20240307-v1:0", input_tokens=0, output_tokens=0
    )
    assert cost == 0.0


def test_compute_cost_for_cross_region_inference_profile_id() -> None:
    """Cross-region IDs bill at the base model rate."""
    base_cost = compute_cost_usd(
        "anthropic.claude-3-haiku-20240307-v1:0",
        input_tokens=1000,
        output_tokens=1000,
    )
    cross_cost = compute_cost_usd(
        "us.anthropic.claude-3-haiku-20240307-v1:0",
        input_tokens=1000,
        output_tokens=1000,
    )
    assert base_cost == cross_cost
