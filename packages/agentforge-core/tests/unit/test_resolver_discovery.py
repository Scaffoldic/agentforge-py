"""Unit tests for entry-point discovery + `list_installed` (feat-010 chunk 1).

The resolver's `resolve` / `list_` / `list_installed` methods all
trigger lazy entry-point discovery. We test against the discovery
of REAL `agentforge.*` entry points the workspace already ships
(e.g. `agentforge.evaluators.correctness` from
`agentforge-eval-geval`, `agentforge.memory.sqlite` from
`agentforge-memory-sqlite`), plus a fake injected via
monkeypatching the `entry_points()` call for edge cases.
"""

from __future__ import annotations

import logging
from importlib.metadata import EntryPoint

import pytest
from agentforge_core import ModuleInfo, Resolver, register
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import discover as discover_mod
from agentforge_core.resolver.discover import (
    discover_entry_points,
    module_info_for,
    reset_discovery,
)
from pydantic import BaseModel


@pytest.fixture(autouse=True)
def _fresh_resolver():
    """Snapshot the global resolver's state, clear it for the test,
    then restore on teardown. We can't just `clear()` and walk away —
    other tests rely on `@register`-fired registrations from
    `agentforge.strategies` etc. that only happen at module import
    time and won't repopulate after a clear."""
    resolver = Resolver.global_()
    saved_registry = dict(resolver._registry)
    saved_module_info = dict(discover_mod._module_info_cache)
    saved_flag = discover_mod._discovered[0]

    resolver.clear()
    try:
        yield
    finally:
        resolver.clear()
        resolver._registry.update(saved_registry)
        discover_mod._module_info_cache.update(saved_module_info)
        discover_mod._discovered[0] = saved_flag


# --- discovery happy path -----------------------------------------


def test_discovery_picks_up_real_workspace_entries():
    """`agentforge-eval-geval` ships `agentforge.evaluators.correctness`
    + co.; `agentforge-memory-sqlite` ships `agentforge.memory.sqlite`.
    Discovery should find both."""
    resolver = Resolver.global_()
    reset_discovery()
    count = discover_entry_points(resolver, force=True)
    assert count > 0

    # Spot-check a few entries we know ship in this workspace.
    entries = {(c, n) for c, n, _ in resolver.list_()}
    assert ("evaluators", "correctness") in entries
    assert ("evaluators", "geval") in entries
    assert ("memory", "sqlite") in entries


def test_list_installed_returns_moduleinfo_for_each():
    resolver = Resolver.global_()
    reset_discovery()
    infos = resolver.list_installed()
    assert all(isinstance(i, ModuleInfo) for i in infos)
    # Entries that came from entry points carry a package + version.
    geval = next(i for i in infos if i.category == "evaluators" and i.name == "correctness")
    assert geval.package == "agentforge-eval-geval"
    assert geval.version  # non-empty
    assert "Correctness" in geval.cls_qualname


def test_list_installed_filters_by_category():
    resolver = Resolver.global_()
    reset_discovery()
    eval_only = resolver.list_installed(category="evaluators")
    assert all(i.category == "evaluators" for i in eval_only)
    # The six named evaluators + geval engine are all entry-point-registered.
    names = {i.name for i in eval_only}
    assert names >= {
        "correctness",
        "faithfulness",
        "groundedness",
        "hallucination",
        "relevance",
        "helpfulness",
        "geval",
    }


def test_resolve_triggers_discovery_lazily():
    """A reset resolver auto-discovers on the next `resolve()`."""
    resolver = Resolver.global_()
    resolver.clear()
    reset_discovery()  # opt back into a fresh scan
    cls = resolver.resolve("evaluators", "correctness")
    assert cls.__name__ == "Correctness"


# --- @register coexists with discovery --------------------------


def test_register_decorator_classes_show_in_list_installed():
    """Classes registered via `@register` (not via entry points) still
    appear in `list_installed`, with `package=None` (no distribution
    backs them)."""

    @register("hooks", "in-process-test-hook")
    class _MyHook:
        pass

    reset_discovery()
    infos = Resolver.global_().list_installed(category="hooks")
    info = next(i for i in infos if i.name == "in-process-test-hook")
    assert info.package is None
    assert info.version is None
    assert info.cls_qualname.endswith("_MyHook")


# --- conflict handling -----------------------------------------


def test_entry_point_conflict_keeps_first_winner(monkeypatch, caplog):
    """When two entry points register under the same `(category,
    name)` pair, the first wins and a WARN is logged."""

    class _First:
        pass

    class _Second:
        pass

    fake_eps = [
        EntryPoint(
            name="dup",
            value="tests.fake:_First",
            group="agentforge.tools",
        ),
        EntryPoint(
            name="dup",
            value="tests.fake:_Second",
            group="agentforge.tools",
        ),
    ]
    # Each EntryPoint needs a `.load()` and a `.dist`; we monkeypatch
    # `load` to return the class and pretend the dist is absent.
    loaders = {"_First": _First, "_Second": _Second}

    def fake_load(self):
        return loaders[self.value.split(":")[-1]]

    monkeypatch.setattr(EntryPoint, "load", fake_load)
    monkeypatch.setattr(EntryPoint, "dist", property(lambda _self: None))
    monkeypatch.setattr(discover_mod, "entry_points", lambda: fake_eps)

    reset_discovery()
    Resolver.global_().clear()
    caplog.set_level(logging.WARNING, logger="agentforge.resolver")
    discover_entry_points(Resolver.global_(), force=True)

    # The first registration wins.
    assert Resolver.global_().resolve("tools", "dup") is _First
    # WARN logged.
    assert any("entry-point conflict" in r.message for r in caplog.records)


def test_load_failure_skipped_and_logged(monkeypatch, caplog):
    """Entry points whose `.load()` raises should be skipped with a
    WARN, not bring down the whole scan."""

    class _Good:
        pass

    good_ep = EntryPoint(name="good", value="x:Good", group="agentforge.tools")
    bad_ep = EntryPoint(name="bad", value="x:Bad", group="agentforge.tools")

    def fake_load(self):
        if self.name == "bad":
            raise ImportError("can't import bad")
        return _Good

    monkeypatch.setattr(EntryPoint, "load", fake_load)
    monkeypatch.setattr(EntryPoint, "dist", property(lambda _self: None))
    monkeypatch.setattr(discover_mod, "entry_points", lambda: [good_ep, bad_ep])

    reset_discovery()
    Resolver.global_().clear()
    caplog.set_level(logging.WARNING, logger="agentforge.resolver")
    discover_entry_points(Resolver.global_(), force=True)

    # Good registered; bad skipped.
    assert Resolver.global_().resolve("tools", "good") is _Good
    with pytest.raises(ModuleError):
        Resolver.global_().resolve("tools", "bad")
    assert any("load failed" in r.message for r in caplog.records)


def test_non_class_entry_point_skipped(monkeypatch, caplog):
    """Entry points that point to a function or instance (not a class)
    are skipped with a WARN."""

    def _not_a_class():
        pass

    bad_ep = EntryPoint(name="bad", value="x:func", group="agentforge.tools")

    monkeypatch.setattr(EntryPoint, "load", lambda _self: _not_a_class)
    monkeypatch.setattr(EntryPoint, "dist", property(lambda _self: None))
    monkeypatch.setattr(discover_mod, "entry_points", lambda: [bad_ep])

    reset_discovery()
    Resolver.global_().clear()
    caplog.set_level(logging.WARNING, logger="agentforge.resolver")
    discover_entry_points(Resolver.global_(), force=True)

    assert any("not a class" in r.message for r in caplog.records)


def test_config_sections_group_excluded_from_resolver(monkeypatch):
    """`agentforge.config_sections` maps app-config sections to pydantic
    schemas (feat-026 Phase 2); the runtime resolver must skip the group
    so schemas never land in the module registry."""

    class _GraphSchema(BaseModel):
        pass

    section_ep = EntryPoint(
        name="graph",
        value="x:GraphSchema",
        group="agentforge.config_sections",
    )
    tool_ep = EntryPoint(name="real", value="x:Real", group="agentforge.tools")

    class _Real:
        pass

    monkeypatch.setattr(
        EntryPoint,
        "load",
        lambda self: _GraphSchema if self.group.endswith("config_sections") else _Real,
    )
    monkeypatch.setattr(EntryPoint, "dist", property(lambda _self: None))
    monkeypatch.setattr(discover_mod, "entry_points", lambda: [section_ep, tool_ep])

    reset_discovery()
    Resolver.global_().clear()
    discover_entry_points(Resolver.global_(), force=True)

    # The tool registered; the config section did NOT leak into the resolver.
    assert Resolver.global_().resolve("tools", "real") is _Real
    with pytest.raises(ModuleError):
        Resolver.global_().resolve("config_sections", "graph")


# --- helper coverage --------------------------------------------


def test_module_info_for_synthesises_when_uncached():
    """For classes that bypass the entry-point path (e.g. registered
    via `@register`), `module_info_for` synthesises a `ModuleInfo`
    from the class's `__module__` / `__qualname__`."""

    class _Local:
        pass

    info = module_info_for("widgets", "x", _Local)
    assert info.category == "widgets"
    assert info.name == "x"
    assert info.package is None
    assert info.version is None
    assert info.cls_qualname.endswith("_Local")
