"""Hypothesis property tests for Bedrock cost calculation.

For any (input_tokens, output_tokens) pair on a known model, the
computed cost must:
  - be non-negative
  - scale linearly with input_tokens
  - scale linearly with output_tokens (when the model has an output rate)
  - equal the base cost regardless of cross-region prefix
"""

from __future__ import annotations

import pytest
from agentforge_bedrock._pricing import compute_cost_usd, lookup
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# A few representative known models — full table is small; we don't
# need to enumerate every row.
_KNOWN_MODELS = [
    "anthropic.claude-3-haiku-20240307-v1:0",
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "anthropic.claude-haiku-4-5-20251001-v1:0",
    "anthropic.claude-sonnet-4-5-20250929-v1:0",
]

_CROSS_REGION_PREFIXES = ["us.", "eu.", "apac.", "global."]


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    input_tokens=st.integers(min_value=0, max_value=1_000_000),
    output_tokens=st.integers(min_value=0, max_value=1_000_000),
    model=st.sampled_from(_KNOWN_MODELS),
)
def test_cost_is_non_negative_and_finite(input_tokens: int, output_tokens: int, model: str) -> None:
    cost = compute_cost_usd(model, input_tokens=input_tokens, output_tokens=output_tokens)
    assert cost >= 0.0
    assert cost == cost  # not NaN  # noqa: PLR0124
    assert cost < float("inf")


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    factor=st.integers(min_value=2, max_value=100),
    base_input=st.integers(min_value=1, max_value=10_000),
    base_output=st.integers(min_value=1, max_value=10_000),
    model=st.sampled_from(_KNOWN_MODELS),
)
def test_cost_scales_linearly_with_token_counts(
    factor: int, base_input: int, base_output: int, model: str
) -> None:
    """If you double the tokens, the cost doubles. (Linear pricing.)"""
    base = compute_cost_usd(model, input_tokens=base_input, output_tokens=base_output)
    scaled = compute_cost_usd(
        model, input_tokens=base_input * factor, output_tokens=base_output * factor
    )
    assert scaled == pytest.approx(base * factor, rel=1e-9)


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    input_tokens=st.integers(min_value=0, max_value=100_000),
    output_tokens=st.integers(min_value=0, max_value=100_000),
    prefix=st.sampled_from(_CROSS_REGION_PREFIXES),
    model=st.sampled_from(_KNOWN_MODELS),
)
def test_cross_region_prefix_does_not_change_cost(
    input_tokens: int, output_tokens: int, prefix: str, model: str
) -> None:
    """`us.<id>`, `eu.<id>`, `apac.<id>`, `global.<id>` all bill at
    the underlying model's rate."""
    base_cost = compute_cost_usd(model, input_tokens=input_tokens, output_tokens=output_tokens)
    cross_cost = compute_cost_usd(
        f"{prefix}{model}",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    assert base_cost == pytest.approx(cross_cost, rel=1e-9)


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    input_tokens=st.integers(min_value=1, max_value=10_000),
    output_tokens=st.integers(min_value=1, max_value=10_000),
    model=st.sampled_from(_KNOWN_MODELS),
)
def test_cost_decomposes_into_input_plus_output(
    input_tokens: int, output_tokens: int, model: str
) -> None:
    """Total cost = input-only cost + output-only cost (no bonus terms)."""
    total = compute_cost_usd(model, input_tokens=input_tokens, output_tokens=output_tokens)
    input_only = compute_cost_usd(model, input_tokens=input_tokens, output_tokens=0)
    output_only = compute_cost_usd(model, input_tokens=0, output_tokens=output_tokens)
    assert total == pytest.approx(input_only + output_only, rel=1e-9)


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(model=st.sampled_from(_KNOWN_MODELS))
def test_cost_is_zero_for_zero_tokens(model: str) -> None:
    assert compute_cost_usd(model, input_tokens=0, output_tokens=0) == 0.0


def test_known_models_resolve_via_lookup() -> None:
    """Sanity: every model in the property test fixture is actually in
    the price table (otherwise the linearity tests would silently
    pass against the unknown-model zero fallback)."""
    for m in _KNOWN_MODELS:
        assert lookup(m) is not None, f"price table missing {m}"
