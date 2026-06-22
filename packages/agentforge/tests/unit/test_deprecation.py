"""Tests for the deprecation registry (enh-006 part 3)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from agentforge import _deprecation
from agentforge._deprecation import Deprecation, deprecated, iter_deprecations


@pytest.fixture
def clean_registry() -> Iterator[None]:
    """Snapshot + restore the global registry so tests don't leak."""
    saved = dict(_deprecation._REGISTRY)
    try:
        yield
    finally:
        _deprecation._REGISTRY.clear()
        _deprecation._REGISTRY.update(saved)


def test_deprecated_warns_and_delegates(clean_registry: None) -> None:
    @deprecated(since="0.4", replacement="new_thing()", ref="enh-006")
    def old_thing(x: int) -> int:
        return x + 1

    with pytest.warns(DeprecationWarning, match=r"use new_thing\(\) instead \(enh-006\)"):
        assert old_thing(41) == 42


def test_deprecated_registers_entry(clean_registry: None) -> None:
    @deprecated(since="0.4", replacement="new_api", ref="enh-006")
    def some_seam() -> None: ...

    match = [d for d in iter_deprecations() if d.qualname.endswith("some_seam")]
    assert len(match) == 1
    dep = match[0]
    assert dep.since == "0.4"
    assert dep.replacement == "new_api"
    assert dep.ref == "enh-006"


def test_iter_deprecations_sorted_by_since_then_qualname(clean_registry: None) -> None:
    _deprecation._REGISTRY.clear()
    _deprecation._REGISTRY.update(
        {
            "b": Deprecation("b", since="0.5", replacement="x", ref="r"),
            "a": Deprecation("a", since="0.4", replacement="x", ref="r"),
            "c": Deprecation("c", since="0.4", replacement="x", ref="r"),
        }
    )
    assert [d.qualname for d in iter_deprecations()] == ["a", "c", "b"]


def test_message_format() -> None:
    dep = Deprecation("Foo.bar", since="0.4", replacement="Foo.baz", ref="enh-006")
    assert dep.message() == "Foo.bar is deprecated since 0.4; use Foo.baz instead (enh-006)."


def test_registry_empty_of_real_seams_by_default() -> None:
    """The framework ships no real deprecations yet — just the machinery.
    Guards against accidentally shipping one without a CHANGELOG note."""
    assert iter_deprecations() == []
