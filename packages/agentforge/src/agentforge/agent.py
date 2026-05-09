"""`Agent` — the framework's top-level orchestrator.

Per feat-001 §4.2 and ADR-0007, the constructor surface is locked.
Adding a kwarg with a safe default is a minor bump; removing or
renaming requires a major bump.

Lifecycle (per ADR-0010):

    Agent.__init__: load config → resolve modules → wire defaults →
                    install RunIdFilter (if configured)
    Agent.run(task): bind RunContext → call strategy.run(state) →
                     run evaluators → fire on_finish → return RunResult
    Agent.close(): release LLM client / memory / hooks (async ctx mgr OK)

feat-001 ships the lifecycle + locked surface; feat-002 adds the
default `ReActLoop`, feat-003 the provider surface, feat-007 the full
fallback chain. The `Agent` constructor stays unchanged across those
features.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import TracebackType

from agentforge_core.contracts.evaluator import Evaluator
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.contracts.tool import Tool
from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.production.exceptions import (
    AgentForgeError,
    BudgetExceeded,
    GuardrailViolation,
    ModuleError,
)
from agentforge_core.production.log_filter import (
    install_run_id_filter,
    uninstall_run_id_filter,
)
from agentforge_core.production.run_context import (
    RunContext,
    bind_run,
    new_run,
    reset_run,
)
from agentforge_core.resolver import Resolver, parse_model_string
from agentforge_core.values.state import AgentState, FinishReason, RunResult

from agentforge.config import AgentForgeConfig, load_config
from agentforge.memory import InMemoryStore
from agentforge.runtime import RUNTIME_KEY, RuntimeContext

StepHook = Callable[..., Awaitable[None] | None]
"""Hook signature: takes a Step, returns awaitable-or-None."""

FinishHook = Callable[..., Awaitable[None] | None]
"""Hook signature: takes a RunResult, returns awaitable-or-None."""


class Agent:
    """Framework-level agent orchestrator.

    The constructor signature is the locked public API; see
    `docs/features/feat-001-core-contracts-and-agent.md` §4.2.
    """

    def __init__(
        self,
        *,
        model: str | LLMClient | None = None,
        tools: list[Tool] | None = None,
        strategy: str | ReasoningStrategy | None = None,
        memory: MemoryStore | None = None,
        evaluators: list[Evaluator] | None = None,
        system_prompt: str | None = None,
        budget_usd: float | None = None,
        max_iterations: int | None = None,
        on_step: StepHook | None = None,
        on_finish: FinishHook | None = None,
        config_path: str | Path | None = None,
        install_log_filter: bool = True,
    ) -> None:
        self._config: AgentForgeConfig = load_config(config_path)

        # Resolve model.
        self._llm: LLMClient | None
        resolved_model = model if model is not None else self._config.agent.model
        self._llm = self._resolve_model(resolved_model)

        # Resolve strategy.
        resolved_strategy = strategy if strategy is not None else self._config.agent.strategy
        self._strategy: ReasoningStrategy = self._resolve_strategy(resolved_strategy)

        # Defaults: in-memory store, no evaluators, no tools.
        self._memory: MemoryStore = memory if memory is not None else InMemoryStore()
        self._tools: list[Tool] = list(tools) if tools is not None else []
        self._evaluators: list[Evaluator] = list(evaluators) if evaluators is not None else []
        self._system_prompt: str | None = (
            system_prompt if system_prompt is not None else self._config.agent.system_prompt
        )

        # Budget — kwargs override config; config overrides Pydantic default.
        cap_usd = budget_usd if budget_usd is not None else self._config.agent.budget_usd
        max_iter = (
            max_iterations if max_iterations is not None else self._config.agent.max_iterations
        )
        self._budget = BudgetPolicy(usd=cap_usd, max_iterations=max_iter)

        self._on_step = on_step
        self._on_finish = on_finish
        self._closed = False

        if install_log_filter and self._config.logging.run_id_filter:
            install_run_id_filter()

    # ------------------------------------------------------------------
    # Resolution helpers (used at construction; raise at startup, P11).
    # ------------------------------------------------------------------

    def _resolve_model(self, model: str | LLMClient | None) -> LLMClient | None:
        if model is None:
            return None
        if isinstance(model, LLMClient):
            return model
        # String — parse "<provider>:<model_id>". Provider lookup is
        # deferred to feat-003; for now we surface a clear error so the
        # developer knows what's missing.
        provider, _ = parse_model_string(model)
        raise ModuleError(
            f"No LLM provider registered for {provider!r}. "
            f"feat-001 ships only the abstraction; install agentforge-{provider} "
            f"(when feat-003 ships) or pass a typed LLMClient instance directly."
        )

    def _resolve_strategy(self, strategy: str | ReasoningStrategy | None) -> ReasoningStrategy:
        if isinstance(strategy, ReasoningStrategy):
            return strategy
        if strategy is None:
            raise ModuleError(
                "No reasoning strategy provided. feat-001 ships only the "
                "ReasoningStrategy ABC; install agentforge[react] (when feat-002 "
                "ships) or pass a custom ReasoningStrategy instance via "
                "Agent(strategy=...)."
            )
        # String name — look up in the resolver (feat-002 will register
        # ReActLoop here when it ships).
        cls = Resolver.global_().resolve("strategies", strategy)
        if not callable(cls):
            raise ModuleError(f"Resolved strategy {strategy!r} is not constructible: {cls!r}.")
        instance = cls()
        if not isinstance(instance, ReasoningStrategy):
            raise ModuleError(
                f"Resolved strategy {strategy!r} ({cls.__name__}) does not "
                f"implement ReasoningStrategy."
            )
        return instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def memory(self) -> MemoryStore:
        return self._memory

    @property
    def tools(self) -> list[Tool]:
        return list(self._tools)

    @property
    def budget(self) -> BudgetPolicy:
        return self._budget

    async def run(self, task: str) -> RunResult:
        """Execute the agent's reasoning loop on `task`.

        Returns:
            A `RunResult` with the agent's output, full trace, and cost.
        """
        if self._closed:
            raise ModuleError("Agent has been closed; create a new instance.")
        ctx: RunContext = new_run(task=task)
        token = bind_run(ctx)
        started_ms = time.monotonic()
        finish_reason: FinishReason = "completed"
        try:
            # Construct a fresh BudgetPolicy per run so per-run mutable
            # state (spent_usd, iteration, error_streak) doesn't leak
            # across runs of the same Agent instance.
            run_budget = BudgetPolicy(
                usd=self._budget.usd,
                max_tokens=self._budget.max_tokens,
                max_iterations=self._budget.max_iterations,
                error_streak_limit=self._budget.error_streak_limit,
            )
            metadata: dict[str, object] = {}
            if self._llm is not None:
                metadata[RUNTIME_KEY] = RuntimeContext(
                    llm=self._llm,
                    tools=tuple(self._tools),
                    memory=self._memory,
                    budget=run_budget,
                    system_prompt=self._system_prompt,
                )
            state = AgentState(
                run_id=ctx.run_id,
                task=task,
                metadata=metadata,
            )
            try:
                await self._strategy.run(state)
            except BudgetExceeded:
                finish_reason = "budget_exceeded"
                raise
            except GuardrailViolation:
                finish_reason = "guardrail"
                raise
            except AgentForgeError:
                finish_reason = "error"
                raise
            duration_ms = int((time.monotonic() - started_ms) * 1000)
            output = self._extract_output(state)
            tokens_in = sum(s.tokens_in for s in state.steps)
            tokens_out = sum(s.tokens_out for s in state.steps)
            result = RunResult(
                output=output,
                steps=tuple(state.steps),
                cost_usd=run_budget.spent_usd,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                run_id=ctx.run_id,
                duration_ms=duration_ms,
                finish_reason=finish_reason,
            )
            await self._fire_finish(result)
            return result
        finally:
            reset_run(token)

    async def close(self) -> None:
        """Release resources held by the agent (LLM, memory, log filter)."""
        if self._closed:
            return
        self._closed = True
        if self._llm is not None:
            await self._llm.close()
        await self._memory.close()
        uninstall_run_id_filter()

    async def __aenter__(self) -> Agent:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    # ------------------------------------------------------------------

    @staticmethod
    def _extract_output(state: AgentState) -> str:
        """Pick the agent's final output from `state.steps`.

        feat-001 uses the simplest rule: the content of the last
        non-system step, stringified. feat-002 strategies will set
        a richer convention.
        """
        for step in reversed(state.steps):
            if step.kind != "system":
                content = step.content
                return content if isinstance(content, str) else str(content)
        return ""

    async def _fire_finish(self, result: RunResult) -> None:
        if self._on_finish is None:
            return
        outcome = self._on_finish(result)
        if outcome is not None and hasattr(outcome, "__await__"):
            await outcome
