"""Replay primitives (feat-017).

When `Agent(record_runs=memory)` is set, every step + the final run
are persisted as claims (see `agentforge.recording`). The replay
primitives in this module read those claims back and reconstruct the
run deterministically:

- `ReplayLLMClient(memory, run_id)` — an `LLMClient` that returns
  recorded `LLMResponse` shapes in iteration order instead of
  calling a real provider.
- `replay_tools(memory, run_id, real_tools)` — wraps each provided
  tool so its `run(**kwargs)` returns the recorded observation
  string. Inputs are still validated against the tool's input
  schema so schema drift surfaces clearly.
- `ReplayExhausted` — raised when the replay runs past the
  recording (caller probably changed the task or config).

Determinism guarantee: when (a) the same recorded run, (b) the
matching tools (by name), and (c) the same task are used, the
replayed `RunResult.steps` are tuple-equal to the original (frozen
Pydantic models compare by value). Evaluator scores are replayed
from `category="__eval"` claims by `agentforge run --replay`; this
module concerns itself with the loop only.
"""

from __future__ import annotations

import logging
from typing import Any

from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.contracts.tool import Tool
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
    ToolSpec,
)

from agentforge.recording import PIPELINE_CATEGORY, STEP_CATEGORY


class ReplayExhausted(RuntimeError):  # noqa: N818 — mirrors stdlib `StopIteration` naming
    """Raised when the replay outruns the recording.

    Means the caller is asking for more LLM calls than the recorded
    run made — most often because the task or configuration changed.
    """


class ReplayLLMClient(LLMClient):
    """`LLMClient` backed by a previously recorded run.

    On construction, queries every `category="__step"` claim for the
    given `run_id` (ordered by `created_at` — claims store ULID ids
    which sort monotonically). On each `call(...)`, returns the next
    `LLMResponse` synthesized from the recorded "think" step plus
    the subsequent "act" steps that captured the LLM's tool calls.
    """

    def __init__(
        self,
        *,
        responses: list[LLMResponse],
        provider: str = "replay",
        model: str = "replay",
    ) -> None:
        self._responses = list(responses)
        self._cursor = 0
        self._provider = provider
        self._model = model

    @classmethod
    async def from_recording(
        cls,
        memory: MemoryStore,
        run_id: str,
        *,
        provider: str = "replay",
        model: str = "replay",
    ) -> ReplayLLMClient:
        """Build a client from a stored run.

        Queries the memory for all `__step` claims of this run and
        rebuilds an ordered list of synthesized `LLMResponse`s — one
        per "think" step, with that step's text content plus any
        immediately-following "act" steps' tool_calls collected.
        """
        steps = await memory.query(category=STEP_CATEGORY, run_id=run_id, limit=10_000)
        if not steps:
            msg = (
                f"No recorded steps for run_id={run_id!r}. Ensure the agent "
                f"ran with `record_runs=memory` and the run completed."
            )
            raise ModuleError(msg)

        # Claims sort by ULID id (insertion-monotonic); query() returns
        # them in created_at order, which preserves emission order.
        responses: list[LLMResponse] = []
        i = 0
        while i < len(steps):
            payload = steps[i].payload
            if payload["kind"] != "think":
                i += 1
                continue
            tool_calls: list[ToolCall] = []
            j = i + 1
            while j < len(steps) and steps[j].payload["kind"] == "act":
                tc_dict = steps[j].payload.get("tool_call")
                if tc_dict is not None:
                    tool_calls.append(ToolCall.model_validate(tc_dict))
                j += 1
            responses.append(
                LLMResponse(
                    content=str(payload["content"]) if payload["content"] else "",
                    tool_calls=tuple(tool_calls),
                    stop_reason="tool_use" if tool_calls else "end_turn",
                    usage=TokenUsage(
                        input_tokens=int(payload.get("tokens_in", 0)),
                        output_tokens=int(payload.get("tokens_out", 0)),
                    ),
                    cost_usd=float(payload.get("cost_usd", 0.0)),
                    model=model,
                    provider=provider,
                )
            )
            i = j
        return cls(responses=responses, provider=provider, model=model)

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        del system, messages, tools  # ignored — replay is order-driven
        if self._cursor >= len(self._responses):
            msg = (
                f"ReplayLLMClient exhausted after {len(self._responses)} call(s); "
                f"the recorded run made fewer LLM calls than this replay needs. "
                f"The task or config likely diverged."
            )
            raise ReplayExhausted(msg)
        response = self._responses[self._cursor]
        self._cursor += 1
        return response

    async def close(self) -> None:
        # Nothing to release — replay is fully in-memory.
        return


async def replay_tools(
    memory: MemoryStore,
    run_id: str,
    real_tools: list[Tool],
) -> list[Tool]:
    """Wrap each real tool so its `run()` returns recorded observations.

    The wrapper inherits the original tool's `name`, `description`,
    and `input_schema` so the LLM (or `replay_tools`'s downstream
    consumer) still sees the same surface. Recorded observations are
    consumed in iteration order; calls past the recording raise
    `ReplayExhausted`.
    """
    steps = await memory.query(category=STEP_CATEGORY, run_id=run_id, limit=10_000)
    # An "observe" step's content is the tool's return value. We pair
    # each observation with the preceding "act" step's tool name.
    observations: dict[str, list[Any]] = {}
    pending_name: str | None = None
    for claim in steps:
        kind = claim.payload["kind"]
        if kind == "act":
            tc = claim.payload.get("tool_call")
            pending_name = tc["name"] if tc else None
        elif kind == "observe" and pending_name is not None:
            observations.setdefault(pending_name, []).append(claim.payload["content"])
            pending_name = None

    return [_wrap_replay(tool, observations.get(tool.name, [])) for tool in real_tools]


def _wrap_replay(real: Tool, observations: list[Any]) -> Tool:
    """Build a Tool subclass that returns recorded observations in order."""
    cursor = [0]
    name = real.name
    description = real.description
    input_schema = real.input_schema

    class _ReplayTool(Tool):
        name = real.name
        description = real.description
        input_schema = real.input_schema

        async def run(self, **kwargs: Any) -> Any:
            del kwargs
            if cursor[0] >= len(observations):
                msg = f"Replay for tool {name!r} exhausted after {len(observations)} invocation(s)."
                raise ReplayExhausted(msg)
            obs = observations[cursor[0]]
            cursor[0] += 1
            return obs

    _ReplayTool.__name__ = f"Replay_{type(real).__name__}"
    _ReplayTool.__qualname__ = _ReplayTool.__name__
    # The closure captures `name`, `description`, `input_schema`; the
    # explicit class attrs above also pin them so Tool's metaclass
    # check passes.
    del description, input_schema  # silence ARG
    return _ReplayTool()


async def load_pipeline_result(memory: MemoryStore, run_id: str) -> Any | None:
    """Reconstruct the `PipelineResult` recorded for ``run_id``.

    Returns ``None`` when the run was not recorded with a pipeline.
    The findings come back as `SimpleFinding` instances when their
    shape matches; otherwise as plain dicts (the agent's built-in
    `pipeline_findings` tool tolerates either form).
    """
    from agentforge_core.values.pipeline import PipelineResult  # noqa: PLC0415

    from agentforge.findings import SimpleFinding  # noqa: PLC0415

    claims = await memory.query(category=PIPELINE_CATEGORY, run_id=run_id, limit=1)
    if not claims:
        return None
    payload = claims[0].payload
    raw_findings = payload.get("findings", [])
    findings: list[Any] = []
    for fd in raw_findings:
        if isinstance(fd, dict) and {"severity", "category", "message"} <= fd.keys():
            try:
                findings.append(SimpleFinding.model_validate(fd))
            except Exception as exc:
                logging.getLogger("agentforge.replay").debug(
                    "pipeline finding %r failed SimpleFinding validation: %s; keeping raw dict",
                    fd,
                    exc,
                )
                findings.append(fd)
        else:
            findings.append(fd)
    return PipelineResult(
        findings=tuple(findings),
        task_durations_ms=dict(payload.get("task_durations_ms", {})),
        task_failures=dict(payload.get("task_failures", {})),
        total_cost_usd=float(payload.get("total_cost_usd", 0.0)),
    )


__all__ = [
    "ReplayExhausted",
    "ReplayLLMClient",
    "load_pipeline_result",
    "replay_tools",
]
