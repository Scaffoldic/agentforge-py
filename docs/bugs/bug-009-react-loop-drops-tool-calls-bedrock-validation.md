---
status: fixed in 0.2.4
severity: P0
found-in: v0.2.3
found-via: live integration test of a Bedrock-backed agent
---

# bug-009 — ReAct loop drops `tool_calls` on assistant messages, Bedrock rejects every tool-using turn

## Symptom

Any tool-using prompt against the `bedrock:` provider with the `react`
strategy fails on iteration 2:

```
agentforge_core.production.exceptions.ProviderError: Bedrock validation:
The number of toolResult blocks at messages.2.content exceeds the number
of toolUse blocks of previous turn.
```

Reproduced 100% of the time on first tool dispatch. Non-tool-using
prompts (LLM answers from prior knowledge with no `tool_calls`) work
fine, so the bug is invisible until the agent actually uses a tool.

## Reproduction

```python
# After `agentforge new my-agent --template minimal --provider bedrock`
# and adding any simple tool to the Agent, run:
from agentforge import Agent, tool

@tool
async def list_grades() -> list[int]:
    """Return the grades available in the bank."""
    return [7, 8, 9]

async with Agent(model="bedrock:us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                 strategy="react",
                 tools=[list_grades]) as agent:
    await agent.run("Which grades are available?")
```

**Expected:** the LLM calls `list_grades`, sees `[7, 8, 9]`, replies with the answer.
**Actual:** `ProviderError: Bedrock validation: The number of toolResult blocks at messages.2.content exceeds the number of toolUse blocks of previous turn.`

## Root cause

Three interacting points in `agentforge-py 0.2.3`:

1. **`Message` has no `tool_calls` field.**
   `agentforge_core/values/messages.py::Message` carries only
   `role, content, name, tool_call_id`. There is nowhere on a
   `Message(role="assistant")` to record the `tool_calls` the LLM emitted.

2. **`ReActLoop.run` discards `response.tool_calls` from the message
   history** (`agentforge/strategies/react.py:86`):

   ```python
   # Record the assistant's turn for the next iteration's context.
   messages.append(Message(role="assistant", content=response.content))
   ```

   The `response.tool_calls` are used to dispatch tools (line 89) but
   never recorded on the appended assistant `Message`.

3. **`_message_to_bedrock` translates each Message in isolation**
   (`agentforge_bedrock/client.py:589-616`). The assistant message becomes
   `{"role": "assistant", "content": [{"text": <text>}]}` — no `toolUse`
   blocks possible. The subsequent `Message(role="tool", tool_call_id=...)`
   becomes `{"role": "user", "content": [{"toolResult": {...}}]}`.

The resulting Bedrock Converse `messages` payload sent on iteration 2:

```
messages[0]  user        [text: <task>]
messages[1]  assistant   [text: <empty or prelude>]      ← NO toolUse
messages[2]  user        [toolResult: ...]               ← orphaned
```

Bedrock's Converse validator rejects this because `messages[2].content`
contains `toolResult` blocks but `messages[1].content` contains zero
`toolUse` blocks.

## Impact

- **Severity P0:** any tool-using agent on Bedrock is non-functional
  with the `react` strategy. ReAct is also the framework-recommended
  default (`runbook 04 — Pick a reasoning strategy`), so this is the
  hot path for most scaffolds with `--provider bedrock`.
- **Workaround feasible:** see § Fix proposal below; downstream consumers
  can monkey-patch, but they need to know the framework's internals to
  do it.
- **Provider scope:** confirmed on Bedrock. OpenAI / Anthropic Direct
  clients likely have the same latent bug — they would also need
  `tool_calls` on the assistant message to round-trip a tool turn — but
  may be more permissive in validation. Worth checking.

## Fix proposal

Three coordinated changes:

1. **Add `tool_calls: tuple[ToolCall, ...] = ()` to `Message`** in
   `agentforge_core/values/messages.py`.
2. **Populate it in `ReActLoop`** (`strategies/react.py:86`):

   ```python
   messages.append(Message(
       role="assistant",
       content=response.content,
       tool_calls=response.tool_calls,
   ))
   ```

   Mirror the same change in any other strategy that re-feeds assistant
   responses (plan-execute, multi-agent, tot).
3. **Emit `toolUse` blocks in `_message_to_bedrock`**
   (`agentforge_bedrock/client.py:589`):

   ```python
   if message.role == "assistant":
       content: list[dict[str, Any]] = []
       if message.content:
           content.append({"text": message.content})
       for tc in message.tool_calls:
           content.append({
               "toolUse": {
                   "toolUseId": tc.id,
                   "name": tc.name,
                   "input": dict(tc.arguments),
               }
           })
       return {"role": "assistant", "content": content}
   ```

The same fix shape applies to the OpenAI and Anthropic-direct clients
(emit `tool_calls` on the assistant message in their native shapes).

## Test to add (regression gate)

- Provider conformance: round-trip a two-iteration ReAct flow against a
  recorded Bedrock cassette where iteration 1 returns a `tool_use`
  stop reason and iteration 2 must include the matching `toolUse`
  block in `messages[1]`.
- ReAct strategy unit test: after one iteration with a tool call,
  assert `messages[-2].tool_calls` is non-empty and matches the prior
  response.

## Notes

- Downstream consumer (a downstream consumer) is shipping a monkey-patch in
  `_patches.py` that smuggles `tool_calls` through
  the unused `Message.name` field as a JSON sentinel. They will remove
  the patch on framework upgrade to the version that fixes this.
- The bug is invisible in unit tests that don't actually call Bedrock
  (the framework's `_build_converse_request` happily builds an invalid
  payload). A provider conformance test that hits the real validator —
  even via VCR cassette — would have caught it. Filed as bug-011 for
  v0.3.

## Fix (shipped in v0.2.4)

All three sub-fixes landed together on `fix/bug-009-react-loop-drops-tool-calls`:

1. **Core** — `agentforge_core.values.messages.Message` gains
   `tool_calls: tuple[ToolCall, ...] = ()` (frozen, default-empty, so
   every existing call site stays valid).
2. **Strategy** — `ReActLoop.run` and `ReActLoop.stream` populate
   the field when appending the assistant turn.
3. **Providers** — `_message_to_bedrock` emits Converse `toolUse`
   blocks; `_message_to_openai` emits the parallel `tool_calls`
   array with JSON-encoded `arguments`; `_message_to_anthropic`
   emits typed `tool_use` content blocks.

Regression tests added per layer (Message round-trip, ReAct run +
stream re-feed, Bedrock toolUseId↔toolResult pairing, OpenAI
tool_calls shape, Anthropic tool_use blocks).
