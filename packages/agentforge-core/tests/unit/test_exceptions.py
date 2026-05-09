"""Unit tests for the AgentForge exception hierarchy."""

from __future__ import annotations

import pytest
from agentforge_core.production.exceptions import (
    AgentForgeError,
    BudgetExceeded,
    CapabilityNotSupported,
    GuardrailViolation,
    ModuleError,
    ProviderError,
)


@pytest.mark.parametrize(
    "subclass",
    [
        BudgetExceeded,
        GuardrailViolation,
        ModuleError,
        ProviderError,
        CapabilityNotSupported,
    ],
)
def test_every_specific_error_subclasses_agentforge_error(
    subclass: type[Exception],
) -> None:
    assert issubclass(subclass, AgentForgeError)


def test_agentforge_error_subclasses_exception() -> None:
    assert issubclass(AgentForgeError, Exception)


@pytest.mark.parametrize(
    "exc_cls",
    [
        AgentForgeError,
        BudgetExceeded,
        GuardrailViolation,
        ModuleError,
        ProviderError,
        CapabilityNotSupported,
    ],
)
def test_message_preserved_through_str(exc_cls: type[Exception]) -> None:
    err = exc_cls("custom message")
    assert str(err) == "custom message"


def test_can_catch_any_specific_error_via_base() -> None:
    with pytest.raises(AgentForgeError):
        raise BudgetExceeded("test")
    with pytest.raises(AgentForgeError):
        raise GuardrailViolation("test")
