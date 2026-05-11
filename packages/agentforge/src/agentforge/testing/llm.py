"""`MockLLMClient` — the v0.1 public scripted-response `LLMClient`.

Richer than the private `_testing.FakeLLMClient`:

- `MockLLMClient.from_script([...])` accepts a list of dict
  "scripted responses" with text / tool_calls / stop_reason / usage
  — far less boilerplate than constructing `LLMResponse` by hand.
- `MockLLMClient.deterministic("answer")` always returns the same
  short response, perfect for the `agent_factory` default.
- `MockLLMClient.from_recording(path)` (added in chunk 3) replays
  a recorded transcript.
- Tracks `call_count` and `tool_calls_observed` (a list of every
  `(tool_name, arguments)` pair the script emitted) so tests can
  assert on what the agent asked the LLM to call.

Implementation defers as much as possible to the existing
`FakeLLMClient` so we share its captured-call ergonomics; the
public surface is what changed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from agentforge_core.contracts.llm import LLMClient
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    StopReason,
    TokenUsage,
    ToolCall,
    ToolSpec,
)

ScriptedResponse = dict[str, Any]
"""Lightweight scripted response.

Keys (all optional except `text`):
- ``text``: str — the assistant's content.
- ``tool_calls``: list[{name, args, id?}] — emitted tool calls.
- ``stop_reason``: "end_turn" | "tool_use" | ... — defaults to
  "tool_use" when tool_calls are present, "end_turn" otherwise.
- ``usage``: {input_tokens, output_tokens, ...} — defaults to a
  small non-zero usage.
- ``cost_usd``, ``model``, ``provider`` — defaults to 0.0 / "mock"
  / "mock".
"""


class MockLLMClient(LLMClient):
    """Scripted-response `LLMClient`. Public test helper."""

    def __init__(
        self,
        *,
        responses: list[LLMResponse],
        provider: str = "mock",
        model: str = "mock",
    ) -> None:
        self._responses = list(responses)
        self._cursor = 0
        self._observed_tool_calls: list[tuple[str, dict[str, Any]]] = []
        self._provider = provider
        self._model = model

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_script(
        cls,
        responses: list[ScriptedResponse],
        *,
        provider: str = "mock",
        model: str = "mock",
    ) -> MockLLMClient:
        """Build a mock from a list of lightweight dict responses."""
        return cls(
            responses=[_scripted_to_llm_response(r, provider, model) for r in responses],
            provider=provider,
            model=model,
        )

    @classmethod
    def from_recording(
        cls,
        path: str,
        *,
        provider: str = "mock",
        model: str = "mock",
    ) -> MockLLMClient:
        """Replay a recording produced by `record_llm`.

        Responses are returned in on-disk order — same as the
        original real-provider sequence. Matching by request hash
        is exposed for callers that need it; the default replay
        is sequential because tests usually exercise the same flow
        as the recording.
        """
        from agentforge.testing.recording import load_recording  # noqa: PLC0415

        _, entries = load_recording(path)
        responses: list[LLMResponse] = []
        for entry in entries:
            resp = dict(entry["response"])
            # Pydantic strict mode requires tuples for tuple-typed
            # fields; JSON serialisation lowered them to lists.
            if isinstance(resp.get("tool_calls"), list):
                resp["tool_calls"] = tuple(resp["tool_calls"])
            responses.append(LLMResponse.model_validate(resp))
        return cls(responses=responses, provider=provider, model=model)

    @classmethod
    def deterministic(
        cls,
        response: str,
        *,
        provider: str = "mock",
        model: str = "mock",
    ) -> MockLLMClient:
        """Always returns the same single-response transcript.

        Useful for `agent_factory()` defaults: a one-shot reply
        with no tool calls, no cost, that lets `Agent.run` complete
        cleanly in unit tests.
        """
        return cls.from_script(
            [{"text": response, "stop_reason": "end_turn"}],
            provider=provider,
            model=model,
        )

    # ------------------------------------------------------------------
    # Observation surface
    # ------------------------------------------------------------------

    @property
    def call_count(self) -> int:
        """Number of `.call()` invocations so far."""
        return self._cursor

    @property
    def tool_calls_observed(self) -> list[tuple[str, dict[str, Any]]]:
        """Every (tool_name, arguments) pair the script has emitted.

        Tests use this to assert on the agent's tool-call sequence
        without having to inspect each `LLMResponse` manually.
        """
        return list(self._observed_tool_calls)

    # ------------------------------------------------------------------
    # LLMClient contract
    # ------------------------------------------------------------------

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        del system, messages, tools
        if self._cursor >= len(self._responses):
            msg = (
                f"MockLLMClient exhausted after {self._cursor} call(s); "
                f"add more scripted responses or check the strategy loop."
            )
            raise ModuleError(msg)
        response = self._responses[self._cursor]
        self._cursor += 1
        for tc in response.tool_calls:
            self._observed_tool_calls.append((tc.name, dict(tc.arguments)))
        return response

    async def close(self) -> None:
        return


def _scripted_to_llm_response(
    spec: ScriptedResponse,
    provider: str,
    model: str,
) -> LLMResponse:
    """Normalise a `ScriptedResponse` dict into an `LLMResponse`."""
    text = spec.get("text", "")
    raw_tool_calls = spec.get("tool_calls", []) or []
    tool_calls = tuple(
        ToolCall(
            id=tc.get("id") or _synth_tool_id(tc),
            name=tc["name"],
            arguments=dict(tc.get("args", tc.get("arguments", {}))),
        )
        for tc in raw_tool_calls
    )
    stop_reason: StopReason = spec.get(
        "stop_reason",
        "tool_use" if tool_calls else "end_turn",
    )
    usage_raw: dict[str, Any] = spec.get("usage") or {}
    usage = TokenUsage(
        input_tokens=int(usage_raw.get("input_tokens", 1)),
        output_tokens=int(usage_raw.get("output_tokens", 1)),
        cache_read_tokens=int(usage_raw.get("cache_read_tokens", 0)),
        cache_write_tokens=int(usage_raw.get("cache_write_tokens", 0)),
        thinking_tokens=int(usage_raw.get("thinking_tokens", 0)),
    )
    return LLMResponse(
        content=text,
        tool_calls=tool_calls,
        stop_reason=stop_reason,
        usage=usage,
        cost_usd=float(spec.get("cost_usd", 0.0)),
        model=spec.get("model", model),
        provider=spec.get("provider", provider),
    )


def _synth_tool_id(tc: dict[str, Any]) -> str:
    """Synthesize a stable tool-call id from name + arguments.

    Real providers always set their own id; the mock fills one in
    when the script omits it so downstream code that keys on
    ToolCall.id keeps working.
    """
    serialised = json.dumps(
        {"name": tc["name"], "args": tc.get("args", tc.get("arguments", {}))},
        sort_keys=True,
    )
    return "mock-" + hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:12]


__all__ = ["MockLLMClient", "ScriptedResponse"]
