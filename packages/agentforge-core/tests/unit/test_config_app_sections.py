"""Unit tests for registered app-config section validation
(feat-026 Phase 2).

A derived agent registers a Pydantic schema per ``app.<section>`` via
the ``agentforge.config_sections`` entry-point group. The framework
validates each registered section that is present in ``app:`` — strictly
— and leaves unregistered sections free-form, mirroring
``validate_module_configs``.
"""

from __future__ import annotations

import logging
from importlib.metadata import EntryPoint

import pytest
from agentforge_core.config import (
    AgentForgeConfig,
    discover_app_sections,
    validate_app_config,
)
from agentforge_core.config import app_sections as app_sections_mod
from agentforge_core.production.exceptions import ModuleError
from pydantic import BaseModel, ConfigDict


class _StoreConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    path: str


class _GraphConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    store: _StoreConfig
    max_hops: int = 3


_SECTIONS = {"graph": _GraphConfig}


# --- validate_app_config with an injected registry ----------------


def test_registered_section_validates_ok() -> None:
    cfg = AgentForgeConfig.model_validate(
        {"app": {"graph": {"store": {"path": ".ckg"}, "max_hops": 4}}}
    )
    # Does not raise.
    validate_app_config(cfg, sections=_SECTIONS)


def test_typo_under_registered_section_raises() -> None:
    cfg = AgentForgeConfig.model_validate(
        {"app": {"graph": {"store": {"path": ".ckg"}, "max_hopz": 4}}}
    )
    with pytest.raises(ModuleError) as exc:
        validate_app_config(cfg, sections=_SECTIONS)
    assert "app.graph" in str(exc.value)


def test_bad_value_under_registered_section_raises() -> None:
    cfg = AgentForgeConfig.model_validate(
        {"app": {"graph": {"store": {"path": ".ckg"}, "max_hops": "lots"}}}
    )
    with pytest.raises(ModuleError):
        validate_app_config(cfg, sections=_SECTIONS)


def test_unregistered_section_left_untouched() -> None:
    """A section nobody registered is free-form — never validated."""
    cfg = AgentForgeConfig.model_validate(
        {"app": {"telemetry": {"anything": "goes", "nested": {"x": 1}}}}
    )
    validate_app_config(cfg, sections=_SECTIONS)  # no graph key → nothing to do


def test_registered_section_absent_from_app_is_skipped() -> None:
    cfg = AgentForgeConfig.model_validate({"app": {}})
    validate_app_config(cfg, sections=_SECTIONS)  # graph registered but absent


def test_empty_registry_is_a_noop() -> None:
    cfg = AgentForgeConfig.model_validate({"app": {"graph": {"whatever": 1}}})
    validate_app_config(cfg, sections={})


# --- discover_app_sections via monkeypatched entry points ---------


def _make_loader(mapping: dict[str, object]):
    def _fake_load(self: EntryPoint) -> object:
        return mapping[self.name]

    return _fake_load


def test_discover_picks_up_basemodel(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = EntryPoint(name="graph", value="x:GraphConfig", group=app_sections_mod.SECTIONS_GROUP)
    monkeypatch.setattr(EntryPoint, "load", _make_loader({"graph": _GraphConfig}))
    monkeypatch.setattr(app_sections_mod, "entry_points", lambda group: [ep])
    found = discover_app_sections()
    assert found == {"graph": _GraphConfig}


def test_discover_skips_non_basemodel(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _not_a_model() -> None: ...

    ep = EntryPoint(name="bad", value="x:func", group=app_sections_mod.SECTIONS_GROUP)
    monkeypatch.setattr(EntryPoint, "load", _make_loader({"bad": _not_a_model}))
    monkeypatch.setattr(app_sections_mod, "entry_points", lambda group: [ep])
    with caplog.at_level(logging.WARNING):
        found = discover_app_sections()
    assert found == {}
    assert "not a pydantic BaseModel" in caplog.text


def test_discover_skips_load_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _boom(self: EntryPoint) -> object:
        raise ImportError("no such package")

    good = EntryPoint(name="graph", value="x:GraphConfig", group=app_sections_mod.SECTIONS_GROUP)
    bad = EntryPoint(name="broken", value="x:Nope", group=app_sections_mod.SECTIONS_GROUP)

    def _load(self: EntryPoint) -> object:
        if self.name == "broken":
            _boom(self)
        return _GraphConfig

    monkeypatch.setattr(EntryPoint, "load", _load)
    monkeypatch.setattr(app_sections_mod, "entry_points", lambda group: [good, bad])
    with caplog.at_level(logging.WARNING):
        found = discover_app_sections()
    assert found == {"graph": _GraphConfig}
    assert "load failed" in caplog.text


def test_discover_first_registration_wins(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class _Other(BaseModel):
        pass

    first = EntryPoint(name="graph", value="x:GraphConfig", group=app_sections_mod.SECTIONS_GROUP)
    second = EntryPoint(name="graph", value="y:Other", group=app_sections_mod.SECTIONS_GROUP)
    monkeypatch.setattr(
        EntryPoint, "load", _make_loader({"graph": _GraphConfig})
    )  # only first matters
    # second.load() would return _Other, but it must never be consulted.
    monkeypatch.setattr(app_sections_mod, "entry_points", lambda group: [first, second])
    with caplog.at_level(logging.WARNING):
        found = discover_app_sections()
    assert found == {"graph": _GraphConfig}
    assert "duplicate app-config section" in caplog.text


def test_validate_app_config_default_discovery_no_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no registered sections, default discovery yields {} and
    validation is a no-op (covers the discovery-path default arg)."""
    monkeypatch.setattr(app_sections_mod, "entry_points", lambda group: [])
    cfg = AgentForgeConfig.model_validate({"app": {"graph": {"store": {"path": ".ckg"}}}})
    validate_app_config(cfg)
