"""`MultiAgentSupervisor` — supervisor delegates to worker strategies.

Per feat-002 §4.4:

  PHASE 1 — DELEGATE
    Supervisor LLM call decides which workers to invoke and what
    subtask each should solve. Returns a typed `_DelegationPlan`
    (Pydantic) listing one `_WorkerAssignment(worker, task)` per
    invocation. Unknown worker names are dropped with a logged
    warning rather than crashing the run.

  PHASE 2 — EXECUTE WORKERS
    Workers run concurrently (asyncio.Semaphore caps at
    `max_parallel_workers`). Each worker receives:
      - A fresh `AgentState` with a derived `run_id`
        (`"{parent_run_id}/{worker}-{idx}"`) and its own
        sub-`task` from the assignment
      - A sub-`RuntimeContext` with a *proportional* `BudgetPolicy`:
        the parent's *remaining* USD is split evenly among workers
        in this batch (so collective worker spend cannot exceed the
        parent's remaining budget)
      - The shared parent `MemoryStore` (workers can publish
        findings to the same store)

    Per-worker spend is committed back to the parent budget after
    the worker finishes (`parent.budget.commit(worker_spend)`),
    keeping accounting accurate at the supervisor level.

    Worker exceptions are caught and recorded as a `delegate` step
    with `metadata={"error": ...}`; the supervisor continues with
    surviving worker outputs.

  PHASE 3 — AGGREGATE
    Supervisor LLM call synthesises worker outputs into the final
    answer. If zero workers produced output (all errored, or
    delegation plan was empty), the supervisor synthesises directly
    from the original task.

Modern: structured Pydantic delegation plan (no free-form parsing);
proportional budget split with parent-budget reconciliation;
graceful degradation on worker failure.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.observability.tracing import get_tracer
from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.values.chat import StreamingEvent
from agentforge_core.values.messages import Message
from agentforge_core.values.state import AgentState
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentforge.resolver_register import register_strategy
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge.strategies._base import StrategyBase, _events_for_new_steps, get_runtime

log = logging.getLogger(__name__)

DELEGATE_SYSTEM_PROMPT = (
    "You are a supervisor coordinating specialist worker agents. The "
    "available workers are listed below with short descriptions. Decide "
    "which workers to invoke and what subtask each should solve. Return "
    "ONLY a JSON object matching this schema (no other text):\n\n"
    '  {{"assignments": [{{"worker": "<name>", "task": "<subtask text>"}}, ...]}}\n\n'
    "Workers available:\n{worker_catalog}\n\n"
    "Rules:\n"
    "- Only assign workers from the list above (case-sensitive).\n"
    "- Each subtask should be self-contained; workers do not see each "
    "other's outputs.\n"
    "- Prefer parallel independent subtasks. You may assign the same "
    "worker more than once if it makes sense."
)

AGGREGATE_SYSTEM_PROMPT = (
    "You are a supervisor synthesising the final answer from your "
    "workers' outputs. Read the user's task and the per-worker results "
    "below, then produce a clear, complete answer to the original task. "
    "Do not introduce claims unsupported by the worker outputs."
)


# ----------------------------------------------------------------------
# LLM I/O schemas
# ----------------------------------------------------------------------


class _WorkerAssignment(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    worker: str = Field(min_length=1)
    task: str = Field(min_length=1)


class _DelegationPlan(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    assignments: list[_WorkerAssignment] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Worker output
# ----------------------------------------------------------------------


class _WorkerResult(BaseModel):
    """Result of one worker invocation, recorded as a `delegate` step."""

    model_config = ConfigDict(frozen=True, strict=True)
    worker: str
    task: str
    output: str = ""
    error: str | None = None
    cost_usd: float = 0.0


# ----------------------------------------------------------------------
# Strategy
# ----------------------------------------------------------------------


@register_strategy("multi-agent")
class MultiAgentSupervisor(StrategyBase):
    """Supervisor that delegates subtasks to worker strategies.

    Per feat-002 §4.2 the constructor surface is locked at v0.1:

    Args:
        workers: Mapping from worker name (used in the delegation
            plan) to a `ReasoningStrategy` instance that solves the
            subtask. The same strategy class can appear under
            different names (e.g. `"researcher"` and `"summariser"`
            both `ReActLoop`s with different system prompts in
            future). Required and non-empty.
        max_parallel_workers: Max workers that may run concurrently.
            Default 4.
        max_rounds: Number of delegation rounds. Default 1 (one
            delegation + one aggregation). Multi-round delegation
            (supervisor revises plan after seeing partial results)
            is reserved for v0.2.
        worker_descriptions: Optional human-readable descriptions
            shown to the supervisor LLM in the delegation prompt.
            Maps worker name → description. Workers not in the dict
            get a generic "general-purpose worker" description.
    """

    def __init__(
        self,
        *,
        workers: dict[str, ReasoningStrategy],
        max_parallel_workers: int = 4,
        max_rounds: int = 1,
        worker_descriptions: dict[str, str] | None = None,
    ) -> None:
        if not workers:
            raise ValueError("workers must be a non-empty dict")
        for name in workers:
            if not name or not isinstance(name, str):
                raise ValueError(f"worker name must be a non-empty string, got {name!r}")
        if max_parallel_workers < 1:
            raise ValueError("max_parallel_workers must be >= 1")
        if max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        self._workers = dict(workers)
        self._max_parallel_workers = max_parallel_workers
        self._max_rounds = max_rounds
        self._worker_descriptions = dict(worker_descriptions or {})

    async def run(self, state: AgentState) -> AgentState:
        runtime = get_runtime(state)
        round_idx = 0
        all_results: list[_WorkerResult] = []
        tracer = get_tracer()

        while round_idx < self._max_rounds:
            with tracer.start_as_current_span(
                "strategy.iteration",
                attributes={
                    "agentforge.iteration": round_idx,
                    "agentforge.strategy": "multi_agent",
                },
            ):
                new_results, should_break = await self._iterate_round(
                    state, runtime, round_idx, all_results
                )
            all_results.extend(new_results)
            round_idx += 1
            if should_break:
                break

        # PHASE 3 — AGGREGATE
        await self._aggregate(state, round_idx + 1, all_results)
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[StreamingEvent]:
        """Per-round streaming override (feat-002 v0.3 polish).

        Mirrors :meth:`run` but yields a ``step`` `StreamingEvent`
        for each step recorded inside a round (delegate plan +
        per-worker outputs; flushed after the round completes),
        then the final aggregate step, then the terminal ``done``.
        """
        runtime = get_runtime(state)
        round_idx = 0
        all_results: list[_WorkerResult] = []
        tracer = get_tracer()
        before = len(state.steps)

        while round_idx < self._max_rounds:
            with tracer.start_as_current_span(
                "strategy.iteration",
                attributes={
                    "agentforge.iteration": round_idx,
                    "agentforge.strategy": "multi_agent",
                },
            ):
                new_results, should_break = await self._iterate_round(
                    state, runtime, round_idx, all_results
                )
            for ev in _events_for_new_steps(state.steps, before):
                yield ev
            before = len(state.steps)
            all_results.extend(new_results)
            round_idx += 1
            if should_break:
                break

        # PHASE 3 — AGGREGATE
        await self._aggregate(state, round_idx + 1, all_results)
        for ev in _events_for_new_steps(state.steps, before):
            yield ev

        yield StreamingEvent(
            kind="done",
            content={
                "run_id": state.run_id,
                "cost_usd": float(runtime.budget.spent_usd),
            },
            metadata={},
        )

    async def _iterate_round(
        self,
        state: AgentState,
        runtime: RuntimeContext,
        round_idx: int,
        prior_results: list[_WorkerResult],
    ) -> tuple[list[_WorkerResult], bool]:
        """Run one delegation round.

        Returns ``(new_results, should_break)``. ``should_break`` is
        True when the supervisor cannot make further progress this
        run — either the delegation plan was empty or every worker
        errored. The caller is responsible for extending the
        aggregate result list and incrementing ``round_idx``.
        """
        self._check_guardrails(state)

        # PHASE 1 — DELEGATE
        plan = await self._delegate(state, round_idx, prior=prior_results)
        assignments = self._filter_assignments(plan.assignments)
        if not assignments:
            log.info(
                "MultiAgentSupervisor: round %d produced no valid "
                "assignments; proceeding to aggregation.",
                round_idx,
            )
            return [], True

        # PHASE 2 — EXECUTE WORKERS (proportional budget split)
        results = await self._execute_workers(state, runtime, assignments, round_idx=round_idx)

        if not any(r.error is None for r in results):
            # Every worker failed in this round; nothing useful to
            # iterate on. Bail out to aggregation rather than
            # spinning the supervisor on the same failure.
            log.warning(
                "MultiAgentSupervisor: every worker errored in round "
                "%d; aggregating with no successful outputs.",
                round_idx,
            )
            return results, True

        return results, False

    # ------------------------------------------------------------------
    # Phase 1 — delegate
    # ------------------------------------------------------------------

    async def _delegate(
        self,
        state: AgentState,
        round_idx: int,
        *,
        prior: list[_WorkerResult],
    ) -> _DelegationPlan:
        """Ask the supervisor LLM for a delegation plan."""
        catalog = "\n".join(
            f"  - {name}: {self._worker_descriptions.get(name, 'general-purpose worker')}"
            for name in self._workers
        )
        prompt = DELEGATE_SYSTEM_PROMPT.format(worker_catalog=catalog)
        messages: list[Message] = [Message(role="user", content=state.task)]
        if prior:
            prior_text = "\n".join(
                f"- {r.worker}: {r.output if r.error is None else f'ERROR: {r.error}'}"
                for r in prior
            )
            messages.append(
                Message(
                    role="assistant",
                    content=f"Prior worker outputs from earlier rounds:\n{prior_text}",
                )
            )
        response = await self._call_llm(
            state,
            iteration=round_idx + 1,
            system=prompt,
            messages=messages,
            kind="plan",
        )
        try:
            return _DelegationPlan.model_validate_json(_strip_code_fences(response.content))
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            log.warning(
                "MultiAgentSupervisor: delegation plan parse failed at round %d: %s",
                round_idx,
                exc,
            )
            return _DelegationPlan(assignments=[])

    def _filter_assignments(self, assignments: list[_WorkerAssignment]) -> list[_WorkerAssignment]:
        """Drop assignments referring to unknown workers (logged)."""
        kept: list[_WorkerAssignment] = []
        for a in assignments:
            if a.worker in self._workers:
                kept.append(a)
            else:
                log.warning(
                    "MultiAgentSupervisor: dropping assignment for unknown worker %r",
                    a.worker,
                )
        return kept

    # ------------------------------------------------------------------
    # Phase 2 — execute workers
    # ------------------------------------------------------------------

    async def _execute_workers(
        self,
        state: AgentState,
        runtime: RuntimeContext,
        assignments: list[_WorkerAssignment],
        *,
        round_idx: int,
    ) -> list[_WorkerResult]:
        """Run all assigned workers in parallel under a semaphore."""
        per_worker_budget = self._derive_per_worker_budget(runtime.budget, len(assignments))
        sem = asyncio.Semaphore(self._max_parallel_workers)

        async def _one(idx: int, assignment: _WorkerAssignment) -> _WorkerResult:
            async with sem:
                return await self._run_worker(
                    state,
                    runtime,
                    assignment,
                    sub_budget_usd=per_worker_budget,
                    idx=idx,
                )

        results = await asyncio.gather(
            *(_one(i, a) for i, a in enumerate(assignments)),
            return_exceptions=False,
        )
        # Record one `delegate` step per worker outcome.
        for r in results:
            content: dict[str, object] = {
                "worker": r.worker,
                "task": r.task,
                "output": r.output,
                "cost_usd": r.cost_usd,
            }
            if r.error is not None:
                content["error"] = r.error
            self._record_step(
                state,
                iteration=round_idx + 1,
                kind="delegate",
                content=content,
                cost_usd=r.cost_usd,
            )
        return list(results)

    def _derive_per_worker_budget(self, parent: BudgetPolicy, n_workers: int) -> float:
        """Split the parent's *remaining* USD evenly among workers."""
        if n_workers <= 0:
            return 0.0
        return parent.remaining_usd() / n_workers

    async def _run_worker(
        self,
        state: AgentState,
        runtime: RuntimeContext,
        assignment: _WorkerAssignment,
        *,
        sub_budget_usd: float,
        idx: int,
    ) -> _WorkerResult:
        """Run a single worker with a sub-RuntimeContext.

        On exception, returns a `_WorkerResult` with `error` populated
        rather than propagating — the supervisor's contract is to keep
        running with surviving workers.
        """
        worker = self._workers[assignment.worker]
        sub_budget = BudgetPolicy(
            usd=sub_budget_usd,
            max_tokens=runtime.budget.max_tokens,
            max_iterations=runtime.budget.max_iterations,
            error_streak_limit=runtime.budget.error_streak_limit,
        )
        sub_runtime = RuntimeContext(
            llm=runtime.llm,
            tools=runtime.tools,
            memory=runtime.memory,
            budget=sub_budget,
            system_prompt=runtime.system_prompt,
        )
        sub_run_id = f"{state.run_id}/{assignment.worker}-{idx}"
        sub_state = AgentState(
            run_id=sub_run_id,
            task=assignment.task,
            metadata={RUNTIME_KEY: sub_runtime},
        )
        try:
            await worker.run(sub_state)
        except Exception as exc:
            # Roll the worker's spend back into the parent budget even on failure.
            runtime.budget.commit(sub_budget.spent_usd, sub_budget.consumed_tokens)
            log.warning(
                "MultiAgentSupervisor: worker %r failed on subtask %r: %s",
                assignment.worker,
                assignment.task,
                exc,
            )
            return _WorkerResult(
                worker=assignment.worker,
                task=assignment.task,
                output="",
                error=f"{type(exc).__name__}: {exc}",
                cost_usd=sub_budget.spent_usd,
            )

        # Reconcile the sub-budget's spend into the parent budget. The
        # _call_llm helper already committed against `sub_budget`; we
        # mirror that into the parent so the supervisor's accounting is
        # accurate (and so subsequent rounds see the spend).
        runtime.budget.commit(sub_budget.spent_usd, sub_budget.consumed_tokens)

        output = _extract_output(sub_state)
        return _WorkerResult(
            worker=assignment.worker,
            task=assignment.task,
            output=output,
            error=None,
            cost_usd=sub_budget.spent_usd,
        )

    # ------------------------------------------------------------------
    # Phase 3 — aggregate
    # ------------------------------------------------------------------

    async def _aggregate(
        self,
        state: AgentState,
        iteration: int,
        results: list[_WorkerResult],
    ) -> None:
        """Synthesise worker outputs into a final answer."""
        if results:
            results_text = "\n\n".join(
                f"--- {r.worker} ({'OK' if r.error is None else 'ERROR'}) ---\n"
                f"Task: {r.task}\n"
                f"Output: {r.output if r.error is None else r.error}"
                for r in results
            )
            assistant_msg = Message(role="assistant", content=f"Worker outputs:\n{results_text}")
            messages: list[Message] = [
                Message(role="user", content=state.task),
                assistant_msg,
            ]
        else:
            messages = [Message(role="user", content=state.task)]

        await self._call_llm(
            state,
            iteration=iteration,
            system=AGGREGATE_SYSTEM_PROMPT,
            messages=messages,
            kind="synthesize",
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _extract_output(sub_state: AgentState) -> str:
    """Pull the final text output from a worker's sub-state.

    Workers terminate with a `synthesize` or `think` step; we take the
    last step's textual content as the worker's output.
    """
    if not sub_state.steps:
        return ""
    last = sub_state.steps[-1]
    content = last.content
    if isinstance(content, str):
        return content
    return json.dumps(content)


def _strip_code_fences(content: str) -> str:
    """Strip ```json ... ``` fences if the LLM wrapped the JSON in them."""
    text = content.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline == -1:
            return text
        body = text[first_newline + 1 :]
        if body.endswith("```"):
            body = body[: -len("```")]
        return body.strip()
    return text


__all__ = ["MultiAgentSupervisor"]
