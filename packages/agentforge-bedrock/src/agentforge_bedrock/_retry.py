"""Bounded exponential backoff with jitter for retryable Bedrock errors.

Backoff schedule: `min(base * 2**attempt, cap) + uniform(0, jitter)`.
Default `base=0.5s`, `cap=30s`, `jitter=1.0s`. The schedule never
exceeds ~30s + jitter regardless of attempt count.

We do NOT retry through the framework's `BudgetPolicy` — retries are
network-level, no LLM call is issued, no cost is committed. The
caller's `BudgetPolicy.check()` runs once per logical call (before
the first attempt); subsequent attempts ride that single check.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

from agentforge_core.production.exceptions import ProviderError

from agentforge_bedrock._errors import is_retryable

log = logging.getLogger(__name__)


async def with_retry[T](
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    base_seconds: float = 0.5,
    cap_seconds: float = 30.0,
    jitter_seconds: float = 1.0,
) -> T:
    """Call `fn()`, retrying retryable provider errors with backoff.

    Args:
        fn: Async zero-arg callable returning the result. Most callers
            wrap a closure that captures the AWS SDK invocation.
        max_retries: Maximum number of retries *after* the first
            attempt (so total attempts is `max_retries + 1`).
        base_seconds: Initial delay between attempt 0 and 1.
        cap_seconds: Upper bound for the exponential schedule.
        jitter_seconds: Maximum random jitter added per delay.

    Raises:
        ProviderError: the underlying call failed and either the error
            is non-retryable or the retry budget is exhausted.
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")

    attempt = 0
    while True:
        try:
            return await fn()
        except ProviderError as exc:
            if attempt >= max_retries or not is_retryable(exc):
                raise
            delay = min(base_seconds * (2**attempt), cap_seconds) + random.uniform(  # noqa: S311 — non-crypto jitter
                0, jitter_seconds
            )
            log.info(
                "agentforge-bedrock: retryable %s on attempt %d/%d; sleeping %.2fs",
                type(exc).__name__,
                attempt + 1,
                max_retries + 1,
                delay,
            )
            await asyncio.sleep(delay)
            attempt += 1
