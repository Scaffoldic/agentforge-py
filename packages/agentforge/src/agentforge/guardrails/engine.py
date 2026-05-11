"""Guardrail engine — runs validators + emits audit events (feat-018).

Glues `InputValidator` / `OutputValidator` / `ToolCallGate` lists to
the agent's lifecycle. `GuardrailEngine` is constructed once per
`Agent` from the config + the framework-wide policy, then:

- `await engine.check_input(content, ctx)` is invoked once at the
  start of `agent.run(task)`.
- The engine wraps the LLM client (`engine.wrap_llm(llm)`) so every
  `.call(...)` output flows through `OutputValidator`s.
- The engine wraps each tool (`engine.wrap_tool(tool)`) so every
  `.run(...)` is gated through `ToolCallGate`s.

All decisions append to `engine.events` (a list of dicts conforming
to `RunResult.guardrail_events` shape) and emit a structured log
record on the `agentforge.audit` channel.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from agentforge_core.config.schema import GuardrailPolicy
from agentforge_core.contracts.guardrails import (
    InputValidator,
    OutputValidator,
    ToolCallGate,
)
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.tool import Tool
from agentforge_core.production.exceptions import GuardrailViolation, ModuleError
from agentforge_core.values.guardrails import ValidationResult
from agentforge_core.values.messages import LLMResponse, Message, ToolSpec

_audit_log = logging.getLogger("agentforge.audit")


class GuardrailEngine:
    """Per-Agent engine that runs validators + records decisions."""

    def __init__(
        self,
        *,
        input_validators: list[InputValidator],
        output_validators: list[OutputValidator],
        tool_gates: list[ToolCallGate],
        policy: GuardrailPolicy,
    ) -> None:
        self._inputs = list(input_validators)
        self._outputs = list(output_validators)
        self._gates = list(tool_gates)
        self._policy = policy
        self.events: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    async def check_input(self, content: str, context: dict[str, Any]) -> str:
        """Run every input validator. Returns the (possibly redacted)
        content for downstream use; raises `GuardrailViolation` on
        block."""
        return await self._run_stage(
            stage="input",
            validators=self._inputs,
            content=content,
            context=context,
            action=self._policy.on_input_violation,
            call=lambda v, c, ctx: v.validate(c, ctx),
        )

    async def check_output(self, content: str, context: dict[str, Any]) -> str:
        """Run every output validator post-LLM call."""
        return await self._run_stage(
            stage="output",
            validators=self._outputs,
            content=content,
            context=context,
            action=self._policy.on_output_violation,
            call=lambda v, c, ctx: v.validate(c, ctx),
        )

    # ------------------------------------------------------------------
    # Wrappers
    # ------------------------------------------------------------------

    def wrap_llm(self, real: LLMClient, context_factory: Callable[[], dict[str, Any]]) -> LLMClient:
        """Wrap a real `LLMClient` so every `.call()` result flows
        through the configured `OutputValidator`s.

        Validators see the model's text content; tool_calls are
        passed through untouched (those go through `ToolCallGate`s
        on dispatch).
        """
        return _GuardedLLMClient(real=real, engine=self, context_factory=context_factory)

    def wrap_tool(self, real: Tool, context_factory: Callable[[], dict[str, Any]]) -> Tool:
        """Wrap a real `Tool` so every `.run(...)` is gated."""
        return _wrap_tool(real, self, context_factory)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run_stage(
        self,
        *,
        stage: str,
        validators: list[Any],
        content: str,
        context: dict[str, Any],
        action: str,
        call: Callable[[Any, str, dict[str, Any]], Awaitable[ValidationResult]],
    ) -> str:
        current = content
        for v in validators:

            async def _call(
                validator: Any = v,
                content_value: str = current,
                ctx: dict[str, Any] = context,
            ) -> ValidationResult:
                return await call(validator, content_value, ctx)

            result = await self._safe_invoke(v, _call)
            self._emit(stage=stage, validator=v, result=result, content=current, action=action)
            if result.passed:
                continue
            if action == "block":
                msg = (
                    f"guardrail block: validator={v.name!r} stage={stage} "
                    f"violations={list(result.violations)!r}"
                )
                raise GuardrailViolation(msg)
            if action == "redact" and result.redacted_content is not None:
                current = result.redacted_content
            # warn / allow: continue without modification
        return current

    async def authorize_tool(
        self,
        tool_name: str,
        tool: Tool,
        args: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        action = self._policy.on_tool_violation
        for gate in self._gates:

            async def _call(g: ToolCallGate = gate) -> ValidationResult:
                return await g.authorize(tool_name, tool, args, context)

            result = await self._safe_invoke(gate, _call)
            self._emit(
                stage="tool",
                validator=gate,
                result=result,
                content=f"{tool_name}:{sorted(args)}",
                action=action,
            )
            if result.passed:
                continue
            if action == "block":
                msg = (
                    f"guardrail block: tool gate={gate.name!r} tool={tool_name!r} "
                    f"violations={list(result.violations)!r}"
                )
                raise GuardrailViolation(msg)

    async def _safe_invoke(
        self,
        validator: Any,
        call: Callable[[], Awaitable[ValidationResult]],
    ) -> ValidationResult:
        try:
            return await call()
        except (RuntimeError, ModuleError, ValueError) as exc:
            if self._policy.fail_open:
                _audit_log.warning(
                    "validator %s raised; fail_open=True so the call proceeds: %s",
                    validator.name,
                    exc,
                )
                return ValidationResult.ok()
            return ValidationResult(
                passed=False,
                score=0.0,
                violations=("validator_error",),
                metadata={"error": str(exc)},
            )

    def _emit(
        self,
        *,
        stage: str,
        validator: Any,
        result: ValidationResult,
        content: str,
        action: str,
    ) -> None:
        event = {
            "stage": stage,
            "validator": validator.name,
            "passed": result.passed,
            "violations": list(result.violations),
            "score": result.score,
            "action": action,
            "content_hash": _hash(content),
        }
        self.events.append(event)
        log = _audit_log.info if result.passed else _audit_log.warning
        log(
            "guardrail %s: %s passed=%s violations=%s action=%s",
            stage,
            validator.name,
            result.passed,
            list(result.violations),
            action,
        )


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


class _GuardedLLMClient(LLMClient):
    """LLM wrapper that runs output validators after each `.call(...)`."""

    def __init__(
        self,
        *,
        real: LLMClient,
        engine: GuardrailEngine,
        context_factory: Callable[[], dict[str, Any]],
    ) -> None:
        self._real = real
        self._engine = engine
        self._ctx = context_factory

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        response = await self._real.call(system, messages, tools)
        if not response.content:
            return response
        validated = await self._engine.check_output(response.content, self._ctx())
        if validated == response.content:
            return response
        return response.model_copy(update={"content": validated})

    async def close(self) -> None:
        await self._real.close()


def _wrap_tool(
    real: Tool,
    engine: GuardrailEngine,
    context_factory: Callable[[], dict[str, Any]],
) -> Tool:
    """Build a per-instance Tool wrapper that consults `engine` before
    forwarding to `real.run(...)`."""

    real_name = type(real).name
    real_description = type(real).description
    real_input_schema = type(real).input_schema
    real_caps = type(real).capabilities

    async def _run(_self: Tool, **kwargs: Any) -> Any:
        await engine.authorize_tool(real_name, real, kwargs, context_factory())
        return await real.run(**kwargs)

    cls_namespace: dict[str, Any] = {
        "name": real_name,
        "description": real_description,
        "input_schema": real_input_schema,
        "capabilities": real_caps,
        "run": _run,
    }
    synthesized = type(f"Guarded_{type(real).__name__}", (Tool,), cls_namespace)
    return synthesized()  # type: ignore[no-any-return]


__all__ = ["GuardrailEngine"]
