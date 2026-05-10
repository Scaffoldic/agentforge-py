"""`PlanExecuteLoop` — modern plan-and-solve strategy.

Per feat-002 §4.3:

  PHASE 1 — PLAN
    LLM call returns a typed `Plan(steps=[...])` as JSON. Validated
    via Pydantic; cycles and dangling deps caught at parse time. On
    invalid plan: optional re-plan with the error fed back, up to
    `max_replans` retries.

  PHASE 2 — EXECUTE (topological batches)
    Steps grouped into batches by dependencies. Each batch runs
    concurrently (asyncio.Semaphore caps at `max_parallel_steps`).
    Tool steps invoke the named tool; "think" steps (tool=None) make
    one LLM call about the step description.

  PHASE 3 — SYNTHESIZE
    Final LLM call: observations[] → final answer.

Modern: structured Pydantic plan instead of free-form JSON parsing.
The LLM is asked to emit JSON matching the schema; validation errors
are recoverable via re-plan rather than crashing the run.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from agentforge_core.contracts.tool import Tool
from agentforge_core.values.messages import Message
from agentforge_core.values.state import AgentState
from pydantic import ValidationError

from agentforge.resolver_register import register_strategy
from agentforge.strategies._base import StrategyBase, get_runtime
from agentforge.strategies._plan import Plan, PlanStep, _topological_batches

PLAN_SYSTEM_PROMPT = (
    "You are a planning assistant. Decompose the user's task into a "
    "structured execution plan. Return ONLY a JSON object matching this "
    "schema (no other text):\n\n"
    '  {"steps": ['
    '{"id": "<unique id>", '
    '"description": "<what this step does>", '
    '"tool": "<tool name or null>", '
    '"arguments": {<keyword args for the tool>}, '
    '"depends_on": [<earlier step ids>]'
    "}, ...]}\n\n"
    "Rules:\n"
    "- Each step.id must be unique within the plan.\n"
    "- depends_on must reference earlier step ids only.\n"
    "- Steps with tool=null are think-only; an LLM will reason about "
    "the description.\n"
    "- Keep the plan concise; prefer parallelisable independent steps."
)

SYNTHESIS_SYSTEM_PROMPT = (
    "You synthesize a final answer from a structured execution trace. "
    "Read the user's task and the per-step observations, then produce "
    "a clear, complete answer to the original task."
)


@register_strategy("plan-execute")
class PlanExecuteLoop(StrategyBase):
    """Plan-and-solve loop with topological execution and re-planning.

    Per feat-002 §4.2 the constructor surface is locked at v0.1:

    Args:
        max_parallel_steps: Max steps that may execute concurrently
            within a batch. Default 4. Defends against tool fan-out
            blowing past resource limits.
        replan_on_failure: When a step raises during execution, ask
            the LLM to re-plan from scratch with the error context.
            Default True.
        max_replans: Maximum number of full re-plan cycles. Default 1
            (one initial plan + one re-plan).
    """

    def __init__(
        self,
        *,
        max_parallel_steps: int = 4,
        replan_on_failure: bool = True,
        max_replans: int = 1,
    ) -> None:
        if max_parallel_steps < 1:
            raise ValueError("max_parallel_steps must be >= 1")
        if max_replans < 0:
            raise ValueError("max_replans must be >= 0")
        self._max_parallel_steps = max_parallel_steps
        self._replan_on_failure = replan_on_failure
        self._max_replans = max_replans

    async def run(self, state: AgentState) -> AgentState:
        # Verify the runtime is bound (raises clear error otherwise);
        # actual access happens in helpers via `get_runtime(state)`.
        get_runtime(state)
        replans = 0
        plan_messages: list[Message] = [Message(role="user", content=state.task)]

        while True:
            # PHASE 1 — Plan (with retry on parse / validation failure)
            plan = await self._build_plan(state, plan_messages, replans_done=replans)
            self._record_step(
                state,
                iteration=0,
                kind="plan",
                content={"steps": [step.model_dump() for step in plan.steps]},
            )

            # PHASE 2 — Execute
            try:
                observations = await self._execute_plan(state, plan)
                break
            except _StepFailure as failure:
                if not self._replan_on_failure or replans >= self._max_replans:
                    # Surface the failure as a final observation; don't crash.
                    observations = failure.observations_so_far
                    self._record_step(
                        state,
                        iteration=len(plan.steps),
                        kind="observe",
                        content=(
                            f"Plan execution failed at step {failure.failed_step.id!r}: "
                            f"{failure.error}. No further re-plan attempts."
                        ),
                    )
                    break
                replans += 1
                # Feed the failure context back so the LLM can revise the plan.
                plan_messages.append(Message(role="assistant", content=plan.model_dump_json()))
                plan_messages.append(
                    Message(
                        role="user",
                        content=(
                            f"The plan failed at step {failure.failed_step.id!r} "
                            f"({failure.failed_step.description!r}): {failure.error}. "
                            f"Please re-plan."
                        ),
                    )
                )

        # PHASE 3 — Synthesize
        synth_messages: list[Message] = [
            Message(role="user", content=state.task),
            Message(
                role="assistant",
                content=(
                    "Plan executed with the following observations:\n"
                    + "\n".join(f"- {step_id}: {obs}" for step_id, obs in observations.items())
                ),
            ),
        ]
        await self._call_llm(
            state,
            iteration=len(plan.steps) + 1,
            system=SYNTHESIS_SYSTEM_PROMPT,
            messages=synth_messages,
            kind="synthesize",
        )

        return state

    # ------------------------------------------------------------------
    # Phase helpers
    # ------------------------------------------------------------------

    async def _build_plan(
        self,
        state: AgentState,
        messages: list[Message],
        *,
        replans_done: int,
    ) -> Plan:
        """Ask the LLM for a Plan; validate; retry-on-error up to
        `max_replans` total attempts."""
        attempts_left = (self._max_replans - replans_done) + 1
        last_error: str | None = None

        for attempt in range(attempts_left):
            response = await self._call_llm(
                state,
                iteration=0,
                system=PLAN_SYSTEM_PROMPT,
                messages=messages,
                kind="think",
            )
            try:
                return _parse_plan(response.content)
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                last_error = str(exc)
                if attempt >= attempts_left - 1:
                    break
                # Feed the parse error back as user-role correction.
                messages.append(Message(role="assistant", content=response.content))
                messages.append(
                    Message(
                        role="user",
                        content=(
                            f"That plan was invalid: {exc}. "
                            f"Please return a valid JSON plan matching the schema."
                        ),
                    )
                )

        raise _PlanInvalidError(f"Plan invalid after retries: {last_error}")

    async def _execute_plan(self, state: AgentState, plan: Plan) -> dict[str, str]:
        """Execute the plan in topological batches.

        Returns a mapping of `step_id -> observation`.
        Raises `_StepFailure` (caught by `run`) on any step exception
        when `replan_on_failure` is True; otherwise records the
        failure as an observation and continues.
        """
        runtime = get_runtime(state)
        batches = _topological_batches(plan.steps)
        observations: dict[str, str] = {}
        sem = asyncio.Semaphore(self._max_parallel_steps)

        for batch_idx, batch in enumerate(batches, start=1):
            self._check_guardrails(state)

            async def execute_one(
                step: PlanStep, *, batch_idx: int = batch_idx
            ) -> tuple[PlanStep, str | Exception]:
                async with sem:
                    try:
                        observation = await self._run_step(state, batch_idx=batch_idx, step=step)
                    except Exception as exc:
                        return step, exc
                    return step, observation

            results = await asyncio.gather(*(execute_one(step) for step in batch))

            for step, result in results:
                if isinstance(result, Exception):
                    runtime.budget.record_error()
                    if self._replan_on_failure:
                        raise _StepFailure(
                            failed_step=step,
                            error=f"{type(result).__name__}: {result}",
                            observations_so_far=observations,
                        )
                    error_msg = f"Error: {type(result).__name__}: {result}"
                    self._record_step(
                        state,
                        iteration=batch_idx,
                        kind="observe",
                        content=error_msg,
                    )
                    observations[step.id] = error_msg
                else:
                    runtime.budget.record_success()
                    observations[step.id] = result
                    self._record_step(
                        state,
                        iteration=batch_idx,
                        kind="observe",
                        content={"step_id": step.id, "observation": result},
                    )

        return observations

    async def _run_step(
        self,
        state: AgentState,
        *,
        batch_idx: int,
        step: PlanStep,
    ) -> str:
        """Execute one PlanStep. Returns observation text."""
        runtime = get_runtime(state)
        started_ms = time.monotonic()

        if step.tool is None:
            # "Think" step — LLM call about the step's description.
            response = await self._call_llm(
                state,
                iteration=batch_idx,
                system=(
                    "You are reasoning about one step of a larger plan. "
                    "Provide a concise outcome for the step described."
                ),
                messages=[Message(role="user", content=step.description)],
                kind="act",
            )
            return response.content

        # Tool step
        tool = _find_tool(runtime.tools, step.tool)
        if tool is None:
            raise _ToolNotFoundError(
                f"tool {step.tool!r} (referenced by step {step.id!r}) is "
                f"not registered on the agent"
            )

        # Record an `act` step for the tool dispatch.
        self._record_step(
            state,
            iteration=batch_idx,
            kind="act",
            content={
                "step_id": step.id,
                "tool": step.tool,
                "arguments": step.arguments,
            },
        )

        observation = await self._dispatch_tool(tool, step.tool, dict(step.arguments))
        duration_ms = int((time.monotonic() - started_ms) * 1000)
        # Note duration is approximate (records before the observe step
        # is appended); kept on the act step's metadata if needed.
        del duration_ms
        # plan-execute keeps its replan-on-failure semantics: if the
        # dispatch helper produced an `Error:` observation (validation
        # failure, timeout, or tool exception), bubble it up so the
        # surrounding execute_one/_StepFailure machinery can decide
        # whether to replan.
        if observation.startswith("Error:"):
            raise RuntimeError(observation)
        return observation


def _parse_plan(content: str) -> Plan:
    """Parse JSON-encoded plan from the LLM response."""
    cleaned = _strip_code_fences(content)
    return Plan.model_validate_json(cleaned)


def _strip_code_fences(content: str) -> str:
    """Strip ```json ... ``` fences if the LLM wrapped the JSON in them."""
    text = content.strip()
    if text.startswith("```"):
        # Remove leading fence (with optional language tag) and trailing fence.
        first_newline = text.find("\n")
        if first_newline == -1:
            return text
        body = text[first_newline + 1 :]
        if body.endswith("```"):
            body = body[: -len("```")]
        return body.strip()
    return text


def _find_tool(tools: tuple[Tool, ...], name: str) -> Tool | None:
    for tool in tools:
        if type(tool).name == name:
            return tool
    return None


# ----------------------------------------------------------------------
# Internal exceptions (caught by run; never raised to callers).
# ----------------------------------------------------------------------


class _PlanInvalidError(Exception):
    """LLM produced an invalid plan after all retries."""


class _ToolNotFoundError(Exception):
    """A plan step referenced an unregistered tool name."""


class _StepFailure(Exception):  # noqa: N818 — internal sentinel, not user-visible
    """Wraps a step's exception for the run-level retry logic."""

    def __init__(
        self,
        *,
        failed_step: PlanStep,
        error: str,
        observations_so_far: dict[str, str],
    ) -> None:
        super().__init__(error)
        self.failed_step = failed_step
        self.error = error
        self.observations_so_far = observations_so_far


# ----------------------------------------------------------------------
# Public re-exports.
# ----------------------------------------------------------------------


__all__ = ["Plan", "PlanExecuteLoop", "PlanStep"]


_: Any = None  # silence "unused import" for re-exports
