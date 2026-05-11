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

import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import TracebackType
from typing import Any

from agentforge_core.contracts.evaluator import EvalResult, Evaluator
from agentforge_core.contracts.graph_store import GraphStore
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.contracts.tool import Tool
from agentforge_core.observability import get_tracer
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
from agentforge_core.production.log_format import (
    install_json_formatter,
    uninstall_json_formatter,
)
from agentforge_core.production.run_context import (
    RunContext,
    bind_run,
    new_run,
    reset_run,
)
from agentforge_core.resolver import Resolver, parse_model_string
from agentforge_core.values.state import AgentState, FinishReason, RunResult, Step

from agentforge.config import AgentForgeConfig, load_config
from agentforge.memory import InMemoryStore
from agentforge.retrieval import Retriever
from agentforge.runtime import RUNTIME_KEY, RuntimeContext

_evaluator_log = logging.getLogger("agentforge.evaluators")
_observability_log = logging.getLogger("agentforge.observability")


StepHook = Callable[..., Awaitable[None] | None]
"""Hook signature: takes a Step, returns awaitable-or-None."""

FinishHook = Callable[..., Awaitable[None] | None]
"""Hook signature: takes a RunResult, returns awaitable-or-None."""

StepHooks = StepHook | list[StepHook]
"""Constructor accepts a single hook or a list. Internally normalised
to a list — see `Agent.__init__`. feat-009 spec §4.4: multiple
observability backends can run concurrently against the same run."""

FinishHooks = FinishHook | list[FinishHook]


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
        retriever: Retriever | None = None,
        graph_store: GraphStore | None = None,
        evaluators: list[Evaluator] | None = None,
        system_prompt: str | None = None,
        budget_usd: float | None = None,
        max_iterations: int | None = None,
        on_step: StepHooks | None = None,
        on_finish: FinishHooks | None = None,
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
        self._retriever: Retriever | None = retriever
        self._graph_store: GraphStore | None = graph_store
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

        self._on_step: list[StepHook] = _normalise_hooks(on_step)
        self._on_finish: list[FinishHook] = _normalise_hooks(on_finish)
        self._closed = False

        if install_log_filter and self._config.logging.run_id_filter:
            install_run_id_filter()
        if install_log_filter and self._config.logging.format == "json":
            install_json_formatter()

    # ------------------------------------------------------------------
    # Resolution helpers (used at construction; raise at startup, P11).
    # ------------------------------------------------------------------

    def _resolve_model(self, model: str | LLMClient | None) -> LLMClient | None:
        if model is None:
            return None
        if isinstance(model, LLMClient):
            return model
        # String — parse "<provider>:<model_id>" and look up the
        # provider in the resolver. feat-003 lights up the bedrock
        # provider; future provider packages (anthropic, openai, ...)
        # register themselves the same way at import time.
        provider, model_id = parse_model_string(model)
        try:
            cls = Resolver.global_().resolve("providers", provider)
        except ModuleError as exc:
            raise ModuleError(
                f"No LLM provider registered for {provider!r}. "
                f"Install agentforge-{provider} (e.g. `uv add agentforge-{provider}`) "
                f"or pass a typed LLMClient instance via Agent(model=...)."
            ) from exc
        instance = cls(model_id=model_id)
        if not isinstance(instance, LLMClient):
            raise ModuleError(
                f"Resolved provider {provider!r} ({cls.__name__}) does not implement LLMClient."
            )
        return instance

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
        # Root span for the whole run. When no OTel SDK is installed
        # this is a no-op `NonRecordingSpan` — near-zero cost. With
        # `agentforge-otel` installed, this becomes the parent of
        # every strategy.iteration / llm.call / tool.<name> span the
        # framework emits.
        tracer = get_tracer()
        try:
            with tracer.start_as_current_span(
                "agent.run",
                attributes={
                    "agentforge.run_id": ctx.run_id,
                    "agentforge.task": task,
                },
            ) as run_span:
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
                        retriever=self._retriever,
                        graph_store=self._graph_store,
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
                finally:
                    # Fire `on_step` for every step the strategy appended,
                    # even on error paths — observability of the partial
                    # trace is just as important as the happy path.
                    await self._fire_steps(list(state.steps))
                duration_ms = int((time.monotonic() - started_ms) * 1000)
                output = self._extract_output(state)
                tokens_in = sum(s.tokens_in for s in state.steps)
                tokens_out = sum(s.tokens_out for s in state.steps)
                interim = RunResult(
                    output=output,
                    steps=tuple(state.steps),
                    cost_usd=run_budget.spent_usd,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    run_id=ctx.run_id,
                    duration_ms=duration_ms,
                    finish_reason=finish_reason,
                )
                eval_scores = await self._run_evaluators(
                    interim, task=task, state=state, budget=run_budget
                )
                result = interim.model_copy(update={"eval_scores": eval_scores})
                # Tag the root span with the run summary before it closes.
                run_span.set_attribute("agentforge.finish_reason", finish_reason)
                run_span.set_attribute("agentforge.cost_usd", result.cost_usd)
                run_span.set_attribute("agentforge.tokens_in", result.tokens_in)
                run_span.set_attribute("agentforge.tokens_out", result.tokens_out)
                run_span.set_attribute("agentforge.duration_ms", result.duration_ms)
                run_span.set_attribute("agentforge.n_steps", len(result.steps))
                await self._fire_finish(result)
                return result
        finally:
            reset_run(token)

    async def _run_evaluators(
        self,
        result: RunResult,
        *,
        task: str,
        state: AgentState,
        budget: BudgetPolicy,
    ) -> tuple[EvalResult, ...]:
        """Iterate configured evaluators, gating each by remaining budget.

        Per feat-006 §4.3: skip an evaluator if
        `budget.remaining_usd() < evaluator.cost_estimate_usd`; log at
        WARN. The evaluator receives the just-built `RunResult` as
        `finding` and a context dict carrying `task`, `state`, and
        `budget` so judge graders can reserve / commit against the
        live policy.

        Skipped evaluators do not appear in the returned tuple — only
        evaluators that actually ran. Order preserved.
        """
        if not self._evaluators:
            return ()

        context: dict[str, object] = {"task": task, "state": state, "budget": budget}
        out: list[EvalResult] = []
        for evaluator in self._evaluators:
            est = float(getattr(evaluator, "cost_estimate_usd", 0.0))
            remaining = budget.remaining_usd()
            if est > remaining:
                _evaluator_log.warning(
                    "skipping evaluator %r: budget exhausted (need=$%.4f, remaining=$%.4f)",
                    evaluator.name,
                    est,
                    remaining,
                )
                continue
            eval_result = await evaluator.evaluate(result, context)
            out.append(eval_result)
        return tuple(out)

    async def close(self) -> None:
        """Release resources held by the agent (LLM, memory, log filter)."""
        if self._closed:
            return
        self._closed = True
        if self._llm is not None:
            await self._llm.close()
        await self._memory.close()
        if self._graph_store is not None:
            await self._graph_store.close()
        uninstall_run_id_filter()
        uninstall_json_formatter()

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
        """Fire every finish hook in registration order. Each hook is
        isolated — a raise gets logged at WARN via the
        `agentforge.observability` logger and does NOT propagate.

        Per feat-009 §4.3: "Observability must never break the run."
        """
        for hook in self._on_finish:
            await _safe_call_hook(hook, result, kind="on_finish")

    async def _fire_steps(self, new_steps: list[Step]) -> None:
        """Fire every step hook for each newly-appended step.

        Order: (step1, hook_a), (step1, hook_b), (step2, hook_a), ...
        — finish each step's hook fan-out before moving to the next.
        Errors are isolated per-hook same as `_fire_finish`.
        """
        if not self._on_step or not new_steps:
            return
        for step in new_steps:
            for hook in self._on_step:
                await _safe_call_hook(hook, step, kind="on_step")


def _normalise_hooks(hooks: Any) -> list[Any]:
    """Accept `None | Callable | list[Callable]`; return a fresh list.

    Centralised so the on_step / on_finish surfaces stay in sync.
    """
    if hooks is None:
        return []
    if isinstance(hooks, list):
        return list(hooks)
    return [hooks]


async def _safe_call_hook(hook: Any, payload: Any, *, kind: str) -> None:
    """Invoke a hook with `payload`; await if it returned an awaitable;
    catch + log any exception so the run keeps going.

    "Observability must never break the run" per feat-009 §4.3.
    """
    try:
        outcome = hook(payload)
        if outcome is not None and hasattr(outcome, "__await__"):
            await outcome
    except Exception as exc:
        _observability_log.warning(
            "hook %s raised %s: %s (hook=%r)",
            kind,
            type(exc).__name__,
            exc,
            getattr(hook, "__name__", hook),
        )
