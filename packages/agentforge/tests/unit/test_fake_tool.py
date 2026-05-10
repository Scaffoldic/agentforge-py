"""Unit tests for `FakeTool` (feat-004 chunk 5)."""

from __future__ import annotations

import pytest
from agentforge._testing import FakeTool
from agentforge_core.contracts.tool import Tool


def test_static_response() -> None:
    fake = FakeTool.fake("web_search", "stub result")
    assert fake.name == "web_search"
    assert isinstance(fake, Tool)


@pytest.mark.asyncio
async def test_static_response_returned_from_run() -> None:
    fake = FakeTool.fake("x", "hello")
    assert await fake.run(any_kwarg="ignored") == "hello"


@pytest.mark.asyncio
async def test_callable_response_receives_kwargs() -> None:
    fake = FakeTool.fake(
        "lookup",
        lambda **kwargs: f"got {kwargs['user_id']}",
    )
    out = await fake.run(user_id="01HX")
    assert out == "got 01HX"


@pytest.mark.asyncio
async def test_async_callable_response() -> None:
    async def _async_fn(**kwargs: object) -> str:
        return f"async-{kwargs['x']}"

    fake = FakeTool.fake("a", _async_fn)
    out = await fake.run(x="value")
    assert out == "async-value"


@pytest.mark.asyncio
async def test_calls_recorded_for_assertions() -> None:
    fake = FakeTool.fake("counter", "ok")
    await fake.run(a=1)
    await fake.run(a=2, b="x")
    assert fake.calls == [{"a": 1}, {"a": 2, "b": "x"}]


def test_per_fake_name_and_description() -> None:
    a = FakeTool.fake("a", "x", description="A tool")
    b = FakeTool.fake("b", "y", description="B tool")
    assert a.name == "a"
    assert a.description == "A tool"
    assert b.name == "b"
    assert b.description == "B tool"


def test_per_fake_capabilities() -> None:
    fake = FakeTool.fake("x", "y", capabilities={"network", "filesystem"})
    assert fake.capabilities == frozenset({"network", "filesystem"})


def test_default_capabilities_empty() -> None:
    fake = FakeTool.fake("x", "y")
    assert fake.capabilities == frozenset()


def test_input_schema_accepts_any_kwargs() -> None:
    """Permissive input schema — the fake doesn't reject odd kwargs.
    Real `Tool` implementations declare strict schemas; the fake is
    intentionally lax so test code can pass anything."""
    fake = FakeTool.fake("x", "y")
    fake.input_schema.model_validate({"any_kwarg": 1, "another": "z"})


def test_to_spec_works() -> None:
    fake = FakeTool.fake("search", "stub", description="Search docs.")
    spec = fake.to_spec()
    assert spec.name == "search"
    assert spec.description == "Search docs."


@pytest.mark.asyncio
async def test_isinstance_tool() -> None:
    """Fakes pass `isinstance(t, Tool)` checks so `Agent(tools=[...])`
    accepts them without special-casing."""
    fake = FakeTool.fake("x", "y")
    assert isinstance(fake, Tool)
