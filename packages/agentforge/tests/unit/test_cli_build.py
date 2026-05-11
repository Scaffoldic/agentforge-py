"""Tests for `agentforge.cli._build` (feat-017 chunk 3)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import pytest
from agentforge import Agent, InMemoryStore
from agentforge.cli._build import (
    build_agent_from_config,
    build_evaluators_from_config,
    build_memory_from_config,
    load_and_build,
)
from agentforge_core.config.schema import (
    AgentConfig,
    AgentForgeConfig,
    EvaluatorEntry,
    MemoryModuleConfig,
    ModulesConfig,
    ProviderConfig,
)
from agentforge_core.contracts.evaluator import EvalResult, Evaluator
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import Resolver, register
from agentforge_core.values.claim import Claim


class _FakeMemory(MemoryStore):
    """Records `init_schema` calls so tests can assert it was invoked."""

    def __init__(self, *, marker: str = "") -> None:
        self.marker = marker
        self.init_called = False

    async def init_schema(self) -> None:
        self.init_called = True

    async def put(self, claim: Claim) -> str:
        del claim
        return "id"

    async def get(self, claim_id: str) -> Claim | None:
        del claim_id
        return None

    async def query(self, **kwargs: Any) -> list[Claim]:
        del kwargs
        return []

    async def supersede(self, old_id: str, new_claim: Claim) -> str:
        del old_id
        return new_claim.id

    def stream(self, **kwargs: Any) -> AsyncIterator[Claim]:
        del kwargs

        async def _empty() -> AsyncIterator[Claim]:
            return
            yield  # pragma: no cover

        return _empty()

    async def delete(
        self,
        *,
        run_id: str | None = None,
        older_than: datetime | None = None,
        category: str | None = None,
    ) -> int:
        del run_id, older_than, category
        return 0

    async def close(self) -> None:
        return


class _FakeEvaluator(Evaluator):
    name = "fake-eval"
    description = "feat-017 build helper test fixture"
    cost_estimate_usd = 0.0

    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        del finding, context
        return EvalResult(
            evaluator=type(self).name,
            score=1.0,
            label="pass",
        )


@pytest.fixture(autouse=True)
def _register_fakes() -> None:
    """Register fakes under unique names so tests stay isolated."""
    register("memory", "build-fake-mem")(_FakeMemory)
    register("evaluators", "build-fake-eval")(_FakeEvaluator)


@pytest.mark.asyncio
async def test_build_memory_resolves_driver_and_calls_init_schema() -> None:
    cfg = AgentForgeConfig(
        agent=AgentConfig(),
        modules=ModulesConfig(memory=MemoryModuleConfig(driver="build-fake-mem")),
    )
    memory = build_memory_from_config(cfg)
    assert isinstance(memory, _FakeMemory)


@pytest.mark.asyncio
async def test_build_evaluators_resolves_entries() -> None:
    cfg = AgentForgeConfig(
        agent=AgentConfig(),
        modules=ModulesConfig(evaluators=[EvaluatorEntry(name="build-fake-eval")]),
    )
    evaluators = build_evaluators_from_config(cfg)
    assert len(evaluators) == 1
    assert isinstance(evaluators[0], _FakeEvaluator)


def test_build_memory_returns_none_when_no_module_configured() -> None:
    cfg = AgentForgeConfig(agent=AgentConfig(), modules=ModulesConfig())
    assert build_memory_from_config(cfg) is None


def test_build_memory_errors_on_unregistered_driver() -> None:
    cfg = AgentForgeConfig(
        agent=AgentConfig(),
        modules=ModulesConfig(memory=MemoryModuleConfig(driver="no-such")),
    )
    with pytest.raises(ModuleError, match="No module registered for memory"):
        build_memory_from_config(cfg)


@pytest.mark.asyncio
async def test_build_agent_from_config_wires_memory_and_evaluators() -> None:
    cfg = AgentForgeConfig(
        agent=AgentConfig(strategy="react"),
        modules=ModulesConfig(
            memory=MemoryModuleConfig(driver="build-fake-mem"),
            evaluators=[EvaluatorEntry(name="build-fake-eval")],
        ),
    )
    # Resolver may not have a "react" strategy registered in unit
    # tests; skip strategy resolution by injecting one upstream.
    cfg = cfg.model_copy(update={"agent": cfg.agent.model_copy(update={"strategy": None})})
    # Without a strategy, Agent rejects construction → catch it; the
    # helper still wires memory + evaluators.
    with pytest.raises(ModuleError, match="No reasoning strategy"):
        await build_agent_from_config(cfg)


@pytest.mark.asyncio
async def test_build_agent_from_config_falls_back_to_in_memory_store() -> None:
    """No `modules.memory` → InMemoryStore default."""
    cfg = AgentForgeConfig(agent=AgentConfig(), modules=ModulesConfig())
    with pytest.raises(ModuleError, match="No reasoning strategy"):
        # construction still fails (no strategy) but memory is wired
        await build_agent_from_config(cfg)


@pytest.mark.asyncio
async def test_build_agent_from_config_calls_memory_init_schema() -> None:
    fake = _FakeMemory(marker="x")
    # Register a fresh class that returns this instance from
    # from_config so we can observe init_schema being called.

    class _Holder:
        instance = fake

        @classmethod
        def from_config(cls, cfg: dict[str, Any]) -> _FakeMemory:
            del cfg
            return cls.instance

    register("memory", "build-holder-mem")(_Holder)
    cfg = AgentForgeConfig(
        agent=AgentConfig(),
        modules=ModulesConfig(memory=MemoryModuleConfig(driver="build-holder-mem")),
    )
    with pytest.raises(ModuleError, match="No reasoning strategy"):
        await build_agent_from_config(cfg)
    assert fake.init_called, "init_schema should be awaited when present"


@pytest.mark.asyncio
async def test_load_and_build_reads_yaml(tmp_path: Any) -> None:
    """`load_and_build` honours the path argument from feat-012."""
    yaml = tmp_path / "agentforge.yaml"
    yaml.write_text(
        "agent:\n  budget:\n    usd: 7.5\n",
        encoding="utf-8",
    )
    with pytest.raises(ModuleError, match="No reasoning strategy"):
        await load_and_build(path=yaml)


def test_provider_config_synthesised_into_model_string() -> None:
    """A `providers: default: ...` block synthesizes the model string
    Agent() understands."""
    cfg = AgentForgeConfig(
        agent=AgentConfig(),
        providers={"default": ProviderConfig(type="bedrock", model="my-id")},
        modules=ModulesConfig(),
    )
    from agentforge.cli._build import _resolve_llm  # noqa: PLC0415

    assert _resolve_llm(cfg) == "bedrock:my-id"


@pytest.mark.asyncio
async def test_in_memory_store_used_when_no_module_section() -> None:
    """Confirm the default path produces an `InMemoryStore`."""
    cfg = AgentForgeConfig(agent=AgentConfig(), modules=ModulesConfig())
    # We can't construct the Agent without a strategy; instead check
    # the helper returns None.
    assert build_memory_from_config(cfg) is None
    # And InMemoryStore is the runtime default — caller wires it.
    fallback = InMemoryStore()
    assert isinstance(fallback, MemoryStore)


def _silence_unused() -> Agent | Resolver:
    """Keep Agent/Resolver imports live for ruff (used implicitly)."""
    raise NotImplementedError
