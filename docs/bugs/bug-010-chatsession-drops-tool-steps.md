---
status: fixed in 0.2.4
severity: P2
found-in: v0.2.3
found-via: live design review for a downstream consumer Generative-UI integration
---

# bug-010 — `ChatSession._run_turn` drops intermediate tool steps from history

## Symptom

When `ChatSession.send(message)` runs an agent that invokes one or
more tools, the persisted `ChatHistoryStore` records only:

- the `user` turn (the inbound message)
- the final `assistant` turn (synthesized natural-language answer)

The intermediate tool steps (`Step(kind="observe", tool_call=...)`)
are present on the in-memory `RunResult.steps` but never written to
the history store. `GET /sessions/{id}/messages` therefore cannot
show what tools ran or what they returned.

## Reproduction

```python
async with Agent(tools=[some_tool]) as agent:
    server = ChatServer(agent_factory=lambda: agent, history_store=SqliteChatHistory.from_path("c.db"), auth=...)
# POST /chat/sessions, then POST /chat/sessions/{id}/messages with a
# prompt that triggers `some_tool`.
# Then SELECT role, content FROM chat_turns ORDER BY timestamp:
#   user       "<prompt>"
#   assistant  "<final text>"
# — no tool row, even though `some_tool` ran and its observation
# shaped the assistant's answer.
```

## Root cause

`agentforge_chat/session.py::ChatSession._run_turn` (lines 188–215):

```python
result = await self._agent.run(task)
...
assistant_turn = await self._persist_assistant(validated_out, result, duration_ms)
```

`_persist_assistant` appends one `ChatTurn(role="assistant")` for the
final `validated_out` text. The framework never iterates
`result.steps` to surface tool calls/observations.

`ChatTurn` itself supports `role="tool"` and `tool_call_id` fields,
so the persistence layer is ready — it's just not invoked.

## Impact

- **Generative-UI clients can't render tool outputs.** Modern chat
  frontends (Anthropic Computer Use, OpenAI Assistants, the
  Generative-UI pattern) dispatch UI cards per tool result by
  fetching the message list and parsing role="tool" turns. With this
  bug, every tool run is invisible after the turn completes — the
  agent's reasoning is lost.
- **Audit / replay / debug.** Without tool turns in history, it's
  impossible to reconstruct what the agent did from chat.db alone.
  Operators must correlate with OTel spans, which is not always
  possible (sampled traces, retention).
- **Severity P2** because a workaround exists (downstream patches
  `_persist_assistant` to also persist `result.steps`), and the
  in-memory `RunResult.steps` is intact during the run.

## Fix proposal

Inside `_persist_assistant`, before appending the assistant turn,
walk `result.steps` and persist tool observations:

```python
for step in result.steps:
    if step.kind == "observe" and step.tool_call is not None:
        await self._history.append(ChatTurn(
            id=uuid4().hex,
            session_id=self._session_id,
            role="tool",
            content=step.content if isinstance(step.content, str) else json.dumps(step.content),
            tool_call_id=step.tool_call.id,
            run_id=result.run_id,
            metadata={"tool_name": step.tool_call.name},
        ))
```

Or, more loosely: persist `kind in ("think","act","observe")` steps
to history under a feature flag (`chat.persist_steps: true` in
agentforge.yaml) so consumers can opt in.

## Test to add

Round-trip test: `ChatSession.send(prompt_that_uses_tools)` then
`history.load(session_id)` returns at least one `ChatTurn(role="tool")`
whose `content` is the tool's observation string and whose
`tool_call_id` matches a value in the prior assistant turn (once
bug-009 is also fixed and assistant turns carry tool_calls in
`metadata`).

## Notes

- Found while implementing the Generative-UI integration in
  `a downstream consumer` ([a downstream consumer gap #3]).
- Workaround: downstream consumers can monkey-patch
  `ChatSession._persist_assistant` to invoke the proposal above.
  a downstream consumer ships such a patch in
  `src/downstream_consumer/_patches.py`; they'll remove it when this
  bug is fixed in the framework.
- Related to bug-009 (assistant turns also drop tool_calls). The
  two together mean: even with bug-010 fixed, you can't tell which
  *assistant* turn produced which tool turns without bug-009 also
  fixed (assistant turn carries the tool_call ids). Both shipped
  together in v0.2.4.

## Fix (shipped in v0.2.4)

Landed on the same branch as bug-009 (`fix/bug-009-react-loop-drops-tool-calls`)
because the two are conceptually paired — bug-009 round-trips
`tool_calls` *within* an agent run; bug-010 round-trips them *across*
chat turns via the persisted `ChatHistoryStore`.

Changes:

1. **`ChatSessionConfig.persist_steps: bool = True`** — new schema
   field (opt-out flag). Default-on because the previous behaviour
   was a silent data loss, not an intentional choice.
2. **`ChatSession.__init__(..., persist_steps: bool = True)`** —
   matching constructor kwarg; threaded by
   `build_chat_session_from_config` from `agentforge.yaml`'s
   `modules.chat.session.persist_steps`.
3. **`ChatSession._persist_steps_from_result(result)`** — walks
   `result.steps`. For each `kind="act"` with `tool_call`, appends
   `ChatTurn(role="assistant", tool_calls=(tool_call,),
   content=json.dumps({"tool":..., "arguments":...}))`. For each
   `kind="observe"` with `tool_call`, appends
   `ChatTurn(role="tool", tool_call_id=..., content=observation)`.
   Called from `_run_turn` BEFORE `_persist_assistant` so the final
   answer is chronologically last.
4. **`ChatSession._persist_steps_from_events(events, run_id=...)`**
   — stream-path mirror. Collects `kind="step"` `StreamingEvent`s
   during `_stream_per_token` and persists them with the same shape.
5. **`strategies._base._events_for_new_steps`** —
   `StreamingEvent.metadata["tool_call"]` now carries the step's
   `tool_call.model_dump()` (when present) so the chat session can
   reconstruct it without reaching into `AgentState`. Additive,
   backwards-compatible.
6. **`ChatResponse.tool_calls`** (synchronous `.send()` return value)
   is now populated from the aggregated `act`-step tool calls instead
   of the previously-hardcoded `()`.

Regression tests (`packages/agentforge-chat/tests/unit/test_session.py`):
- `test_persist_steps_records_act_and_observe_turns`
- `test_response_tool_calls_populated_from_steps`
- `test_persist_steps_false_keeps_history_lean`
- `test_stream_persists_step_turns`
