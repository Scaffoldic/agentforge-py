"""Unit tests for the bounded-backoff retry helper."""

from __future__ import annotations

import asyncio

import pytest
from agentforge_bedrock import _retry
from agentforge_bedrock._retry import with_retry
from agentforge_core.production.exceptions import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    ServiceError,
)


@pytest.fixture(autouse=True)
def patched_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace asyncio.sleep so tests run instantly. Returns the list
    of slept-for durations so tests can assert backoff happened."""
    sleeps: list[float] = []

    async def _record(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(_retry.asyncio, "sleep", _record)
    return sleeps


@pytest.mark.asyncio
async def test_returns_first_success_no_retry(patched_sleep: list[float]) -> None:
    calls = 0

    async def _fn() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = await with_retry(_fn, max_retries=3)
    assert result == "ok"
    assert calls == 1
    assert patched_sleep == []


@pytest.mark.asyncio
async def test_retries_until_success(patched_sleep: list[float]) -> None:
    attempts = 0

    async def _fn() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RateLimitError("throttled")
        return "ok"

    result = await with_retry(_fn, max_retries=5)
    assert result == "ok"
    assert attempts == 3
    assert len(patched_sleep) == 2  # 2 backoffs between 3 attempts


@pytest.mark.asyncio
async def test_exhausts_retries_and_re_raises(patched_sleep: list[float]) -> None:
    async def _fn() -> str:
        raise ServiceError("flaky")

    with pytest.raises(ServiceError):
        await with_retry(_fn, max_retries=2)


@pytest.mark.asyncio
async def test_non_retryable_error_does_not_retry(patched_sleep: list[float]) -> None:
    attempts = 0

    async def _fn() -> str:
        nonlocal attempts
        attempts += 1
        raise AuthenticationError("denied")

    with pytest.raises(AuthenticationError):
        await with_retry(_fn, max_retries=5)
    assert attempts == 1
    assert patched_sleep == []


@pytest.mark.asyncio
async def test_backoff_grows_exponentially_capped(patched_sleep: list[float]) -> None:
    async def _fn() -> str:
        raise RateLimitError("x")

    with pytest.raises(RateLimitError):
        await with_retry(_fn, max_retries=4, base_seconds=1.0, cap_seconds=4.0, jitter_seconds=0.0)
    # 4 retries → 4 sleeps. base=1, cap=4, jitter=0:
    #   attempt 0 -> 1, attempt 1 -> 2, attempt 2 -> 4, attempt 3 -> 4 (capped)
    assert patched_sleep == [1.0, 2.0, 4.0, 4.0]


@pytest.mark.asyncio
async def test_max_retries_zero_means_one_attempt_total() -> None:
    attempts = 0

    async def _fn() -> str:
        nonlocal attempts
        attempts += 1
        raise RateLimitError("x")

    with pytest.raises(RateLimitError):
        await with_retry(_fn, max_retries=0)
    assert attempts == 1


@pytest.mark.asyncio
async def test_negative_max_retries_rejected() -> None:
    async def _fn() -> str:
        return "x"

    with pytest.raises(ValueError, match="max_retries"):
        await with_retry(_fn, max_retries=-1)


@pytest.mark.asyncio
async def test_jitter_adds_random_component(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jitter is `uniform(0, jitter_seconds)`. Pin it to a known value
    and assert the sleep includes it."""
    sleeps: list[float] = []

    async def _record(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(_retry.asyncio, "sleep", _record)
    monkeypatch.setattr(_retry.random, "uniform", lambda _a, _b: 0.5)

    async def _fn() -> str:
        raise RateLimitError("x")

    with pytest.raises(RateLimitError):
        await with_retry(_fn, max_retries=1, base_seconds=1.0, cap_seconds=10.0, jitter_seconds=1.0)
    # base=1, jitter=0.5 → 1.5
    assert sleeps == [1.5]


@pytest.mark.asyncio
async def test_unknown_provider_error_subclass_is_not_retryable() -> None:
    attempts = 0

    async def _fn() -> str:
        nonlocal attempts
        attempts += 1
        raise ProviderError("unknown")

    with pytest.raises(ProviderError):
        await with_retry(_fn, max_retries=5)
    assert attempts == 1


@pytest.mark.asyncio
async def test_caller_can_propagate_non_provider_exception(
    patched_sleep: list[float],
) -> None:
    """Non-`ProviderError` exceptions propagate immediately (no retry)."""

    async def _fn() -> str:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await with_retry(_fn, max_retries=5)
    assert patched_sleep == []
