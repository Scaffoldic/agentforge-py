"""Unit tests for `RuntimeContext` + `RUNTIME_KEY`."""

from __future__ import annotations

import pytest
from agentforge import InMemoryStore
from agentforge._testing import FakeLLMClient
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge_core import BudgetPolicy


def _make_runtime() -> RuntimeContext:
    return RuntimeContext(
        llm=FakeLLMClient(responses=[]),
        tools=(),
        memory=InMemoryStore(),
        budget=BudgetPolicy(),
    )


def test_runtime_context_stores_components() -> None:
    rt = _make_runtime()
    assert isinstance(rt.llm, FakeLLMClient)
    assert rt.tools == ()
    assert isinstance(rt.memory, InMemoryStore)
    assert isinstance(rt.budget, BudgetPolicy)
    assert rt.system_prompt is None


def test_runtime_context_is_frozen() -> None:
    rt = _make_runtime()
    with pytest.raises((AttributeError, Exception)):
        rt.system_prompt = "different"  # type: ignore[misc]


def test_runtime_context_uses_slots() -> None:
    rt = _make_runtime()
    assert not hasattr(rt, "__dict__")


def test_runtime_key_is_stable_string() -> None:
    """The metadata key is part of the framework's internal API; pin it
    via a regression test so an accidental rename surfaces."""
    assert RUNTIME_KEY == "__agentforge_runtime__"


def test_system_prompt_optional() -> None:
    rt = _make_runtime()
    assert rt.system_prompt is None
    rt2 = RuntimeContext(
        llm=FakeLLMClient(),
        tools=(),
        memory=InMemoryStore(),
        budget=BudgetPolicy(),
        system_prompt="You are careful.",
    )
    assert rt2.system_prompt == "You are careful."
