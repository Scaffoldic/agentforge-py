"""Unit tests for `validate_module_configs` (feat-012 chunk 7)."""

from __future__ import annotations

from typing import ClassVar

import pytest
from agentforge_core import register
from agentforge_core.config import (
    AgentForgeConfig,
    EvaluatorEntry,
    MemoryModuleConfig,
    ModulesConfig,
    validate_module_configs,
)
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import Resolver
from agentforge_core.resolver import discover as discover_mod
from agentforge_core.resolver.discover import reset_discovery
from pydantic import BaseModel, ConfigDict, Field


@pytest.fixture(autouse=True)
def _resolver_snapshot():
    """Snapshot resolver state + discovery state so per-test
    `@register` calls don't leak into sibling tests that depend on
    the global entry-point discovery."""
    resolver = Resolver.global_()
    resolver.list_installed()  # ensure discovery has run before snapshot
    saved_registry = dict(resolver._registry)
    saved_module_info = dict(discover_mod._module_info_cache)
    saved_flag = discover_mod._discovered[0]
    yield
    resolver.clear()
    resolver._registry.update(saved_registry)
    discover_mod._module_info_cache.clear()
    discover_mod._module_info_cache.update(saved_module_info)
    discover_mod._discovered[0] = saved_flag


# --- module with a config_schema ----------------------------------


class _PostgresConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    dsn: str
    pool_min: int = Field(default=1, ge=1)


class _FakePostgresStore:
    config_schema: ClassVar[type[BaseModel]] = _PostgresConfig


def test_memory_module_valid_config_passes():
    register("memory", "postgres-test")(_FakePostgresStore)
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            memory=MemoryModuleConfig(
                driver="postgres-test",
                config={"dsn": "postgresql://x"},
            )
        )
    )
    # Should not raise.
    validate_module_configs(cfg)


def test_memory_module_invalid_config_raises():
    register("memory", "postgres-test")(_FakePostgresStore)
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            memory=MemoryModuleConfig(
                driver="postgres-test",
                config={"dsn": 42},  # wrong type
            )
        )
    )
    with pytest.raises(ModuleError, match=r"modules\.memory\.config"):
        validate_module_configs(cfg)


def test_memory_module_extra_field_rejected():
    register("memory", "postgres-test")(_FakePostgresStore)
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            memory=MemoryModuleConfig(
                driver="postgres-test",
                config={"dsn": "ok", "bogus": True},
            )
        )
    )
    with pytest.raises(ModuleError, match="bogus"):
        validate_module_configs(cfg)


# --- module without a config_schema (no-op) ----------------------


class _UnschemaedStore:
    """Module that doesn't declare `config_schema` — config dict is
    accepted as-is."""


def test_module_without_schema_accepts_any_config():
    register("memory", "wild")(_UnschemaedStore)
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            memory=MemoryModuleConfig(
                driver="wild",
                config={"anything": "goes", "really": True},
            )
        )
    )
    validate_module_configs(cfg)  # no raise


# --- missing module --------------------------------------------


def test_missing_module_strict_raises():
    cfg = AgentForgeConfig(
        modules=ModulesConfig(memory=MemoryModuleConfig(driver="nonexistent", config={}))
    )
    with pytest.raises(ModuleError, match="No module registered"):
        validate_module_configs(cfg)


def test_missing_module_non_strict_skipped():
    """`agentforge config validate` against a YAML that references
    not-yet-installed packages: lenient mode skips."""
    reset_discovery()
    cfg = AgentForgeConfig(
        modules=ModulesConfig(memory=MemoryModuleConfig(driver="nonexistent", config={}))
    )
    validate_module_configs(cfg, strict=False)  # no raise


# --- evaluators / observability (named-list shape) --------------


class _CorrectnessConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    ground_truth_field: str = "expected"


class _FakeCorrectness:
    config_schema: ClassVar[type[BaseModel]] = _CorrectnessConfig


def test_evaluator_entry_validated():
    register("evaluators", "correctness-test")(_FakeCorrectness)
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            evaluators=[
                EvaluatorEntry(name="correctness-test", config={"ground_truth_field": "ref"}),
            ]
        )
    )
    validate_module_configs(cfg)  # no raise


def test_evaluator_entry_invalid_config_raises():
    register("evaluators", "correctness-test")(_FakeCorrectness)
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            evaluators=[
                EvaluatorEntry(name="correctness-test", config={"unknown": "x"}),
            ]
        )
    )
    with pytest.raises(ModuleError, match=r"modules\.evaluators\['correctness-test'\]"):
        validate_module_configs(cfg)


# --- bug-019: terse string / single-key-mapping sugar normalises ----


def test_evaluators_accept_all_three_sugar_forms() -> None:
    """String, single-key-mapping, and canonical forms all parse from raw
    YAML-shaped dicts (bug-019)."""
    modules = ModulesConfig.model_validate(
        {
            "evaluators": [
                "faithfulness",  # string sugar
                {"geval": {"rubric": "be nice"}},  # single-key mapping sugar
                {"name": "correctness", "config": {"ground_truth_field": "ref"}},  # canonical
            ]
        }
    )
    assert [(e.name, e.config) for e in modules.evaluators] == [
        ("faithfulness", {}),
        ("geval", {"rubric": "be nice"}),
        ("correctness", {"ground_truth_field": "ref"}),
    ]


@pytest.mark.parametrize("gate", ["input", "output", "tool_gates"])
def test_guardrail_gates_accept_all_three_sugar_forms(gate: str) -> None:
    modules = ModulesConfig.model_validate(
        {
            "guardrails": {
                gate: [
                    "prompt_injection_basic",  # string sugar
                    {"presidio": {"entities": ["EMAIL_ADDRESS"]}},  # single-key mapping sugar
                    {"name": "capability_check", "config": {}},  # canonical
                ]
            }
        }
    )
    entries = getattr(modules.guardrails, gate)
    assert [(e.name, e.config) for e in entries] == [
        ("prompt_injection_basic", {}),
        ("presidio", {"entities": ["EMAIL_ADDRESS"]}),
        ("capability_check", {}),
    ]


def test_string_sugar_rejects_empty_name() -> None:
    """An empty string still fails (name has min_length=1)."""
    with pytest.raises(ValueError, match="evaluators"):
        ModulesConfig.model_validate({"evaluators": [""]})


def test_canonical_form_still_forbids_extra_keys() -> None:
    """Normalisation must not loosen strict/extra=forbid for canonical dicts."""
    with pytest.raises(ValueError, match="evaluators"):
        ModulesConfig.model_validate({"evaluators": [{"name": "x", "config": {}, "bogus": 1}]})


# --- non-class schema attribute (defensive) --------------------


class _BogusSchemaStore:
    """`config_schema` is not a class — validator should treat it as
    None and accept any config rather than crash."""

    config_schema = "not a class"  # type: ignore[assignment]


def test_non_class_schema_attribute_treated_as_none():
    register("memory", "bogus-schema")(_BogusSchemaStore)
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            memory=MemoryModuleConfig(driver="bogus-schema", config={"x": 1}),
        )
    )
    validate_module_configs(cfg)  # no raise
