"""Unit tests for the feat-003 provider-error subclasses."""

from __future__ import annotations

import pytest
from agentforge_core.production.exceptions import (
    AgentForgeError,
    AuthenticationError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    ServiceError,
    TimeoutError,
)


@pytest.mark.parametrize(
    "exc_cls",
    [
        RateLimitError,
        AuthenticationError,
        ModelNotFoundError,
        ServiceError,
        TimeoutError,
    ],
)
def test_provider_error_subclasses_inherit_from_provider_error(
    exc_cls: type[Exception],
) -> None:
    """Every provider-error variant subclasses `ProviderError`."""
    assert issubclass(exc_cls, ProviderError)


@pytest.mark.parametrize(
    "exc_cls",
    [
        RateLimitError,
        AuthenticationError,
        ModelNotFoundError,
        ServiceError,
        TimeoutError,
    ],
)
def test_provider_error_subclasses_inherit_from_agentforge_error(
    exc_cls: type[Exception],
) -> None:
    """`ProviderError` itself subclasses `AgentForgeError`, so the
    framework-wide `except AgentForgeError` catches every provider
    failure."""
    assert issubclass(exc_cls, AgentForgeError)


def test_timeout_error_does_not_subclass_builtin_oserror() -> None:
    """The framework's `TimeoutError` shadows the stdlib name on
    purpose — but it must NOT subclass `OSError` (the builtin), so
    code that catches `OSError` doesn't accidentally catch our
    provider timeout."""
    assert not issubclass(TimeoutError, OSError)


def test_provider_errors_are_raisable_with_a_message() -> None:
    for exc_cls in (
        RateLimitError,
        AuthenticationError,
        ModelNotFoundError,
        ServiceError,
        TimeoutError,
    ):
        with pytest.raises(exc_cls, match="hello"):
            raise exc_cls("hello")


def test_provider_errors_are_distinguishable() -> None:
    """Callers can branch on subclass to retry rate-limit but not
    auth errors."""
    rl = RateLimitError("throttled")
    assert isinstance(rl, RateLimitError)
    assert not isinstance(rl, AuthenticationError)
