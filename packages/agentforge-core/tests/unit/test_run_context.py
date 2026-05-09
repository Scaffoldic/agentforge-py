"""Unit tests for `RunContext`, `current_run`, and the ContextVar."""

from __future__ import annotations

import asyncio

import pytest
from agentforge_core.production.run_context import (
    RunContext,
    bind_run,
    current_run,
    new_run,
    reset_run,
)
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError as _PydValidationError


def test_new_run_assigns_ulid() -> None:
    ctx = new_run()
    # ULIDs are 26-char Base32 (Crockford).
    assert isinstance(ctx.run_id, str)
    assert len(ctx.run_id) == 26


def test_new_run_seeds_idempotency() -> None:
    ctx = new_run(task="hello")
    assert isinstance(ctx.idempotency_seed, str)
    assert len(ctx.idempotency_seed) == 32


def test_new_run_distinct_ids() -> None:
    a = new_run()
    b = new_run()
    assert a.run_id != b.run_id


def test_idempotency_key_stable_for_same_parts() -> None:
    ctx = new_run()
    k1 = ctx.idempotency_key_for("charge", "customer-42")
    k2 = ctx.idempotency_key_for("charge", "customer-42")
    assert k1 == k2


def test_idempotency_key_differs_for_different_parts() -> None:
    ctx = new_run()
    k1 = ctx.idempotency_key_for("charge", "customer-42")
    k2 = ctx.idempotency_key_for("charge", "customer-99")
    assert k1 != k2


def test_idempotency_keys_differ_across_runs_for_same_parts() -> None:
    a = new_run()
    b = new_run()
    assert a.idempotency_key_for("op", 1) != b.idempotency_key_for("op", 1)


def test_idempotency_key_is_64_hex_chars() -> None:
    ctx = new_run()
    key = ctx.idempotency_key_for("anything")
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_current_run_raises_when_no_run_active() -> None:
    with pytest.raises(RuntimeError, match="No active RunContext"):
        current_run()


def test_bind_and_reset_run() -> None:
    ctx = new_run()
    token = bind_run(ctx)
    try:
        assert current_run() is ctx
    finally:
        reset_run(token)
    with pytest.raises(RuntimeError):
        current_run()


@pytest.mark.asyncio
async def test_run_id_propagates_across_nested_async_tasks() -> None:
    """ContextVar must follow asyncio tasks (per Python docs)."""
    ctx = new_run()
    token = bind_run(ctx)
    try:

        async def nested() -> str:
            return current_run().run_id

        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(nested())
            t2 = tg.create_task(nested())
        assert t1.result() == ctx.run_id
        assert t2.result() == ctx.run_id
    finally:
        reset_run(token)


@pytest.mark.asyncio
async def test_concurrent_runs_isolated() -> None:
    """Two concurrent agent runs must see distinct contexts."""
    ctx_a = new_run()
    ctx_b = new_run()

    async def run_with(ctx: RunContext) -> str:
        token = bind_run(ctx)
        try:
            await asyncio.sleep(0)  # let scheduler interleave
            return current_run().run_id
        finally:
            reset_run(token)

    a, b = await asyncio.gather(run_with(ctx_a), run_with(ctx_b))
    assert a == ctx_a.run_id
    assert b == ctx_b.run_id


def test_run_context_is_immutable_for_run_id() -> None:
    """Strict mode rejects type errors; assignment validated."""
    ctx = new_run()
    with pytest.raises(_PydValidationError):
        ctx.run_id = 12345  # type: ignore[assignment]


@given(parts=st.lists(st.one_of(st.integers(), st.text(max_size=20)), max_size=5))
def test_property_idempotency_keys_deterministic(parts: list[object]) -> None:
    """For any parts, calling idempotency_key_for twice returns the same key."""
    ctx = new_run()
    a = ctx.idempotency_key_for(*parts)
    b = ctx.idempotency_key_for(*parts)
    assert a == b
