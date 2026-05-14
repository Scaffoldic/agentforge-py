# 21 — Use streaming guardrails (sentence-window)

> **Goal:** stream tokens to your end-user while still running
> the output guardrails — so PII or unsafe content never
> reaches the client mid-stream.
> **Time:** ~5 minutes.
> **Prereqs:** runbooks 11 + 20 (chat sessions + guardrails).

## TL;DR

```yaml
# agentforge.yaml
modules:
  chat:
    session:
      safety_mode: sentence-window     # the new bit
```

```python
async for chunk in session.stream(turn):
    # `chunk.content` is sentence-sized — never per-token.
    # Output validators have already vetted (and possibly
    # redacted) the text before you see it.
    await client.send(chunk.content)
```

## Step by step

1. **Decide your latency / safety trade-off.** Three
   `safety_mode` settings on `ChatSession`:
   - `buffer-then-stream` (default) — agent finishes, output
     validators run once on the full answer, the chat layer
     segments the result for the wire. Safe, smooth — but the
     user sees zero tokens until the run finishes.
   - `sentence-window` — each token is buffered until a
     sentence boundary; the completed sentence runs through
     `OutputValidator.check_output`; the validated text emits
     downstream. Mid-latency, safe.
   - `stream-then-redact` — currently aliases sentence-window;
     v0.3 may add inline-regex redaction without buffering.
2. **Set `modules.chat.session.safety_mode: sentence-window`**
   in `agentforge.yaml`. `build_chat_session_from_config`
   forwards the value into `ChatSession(safety_mode=...)`.
3. **Make sure your `OutputValidator`s are sentence-friendly.**
   Validators like `pii_redact_basic` work per-sentence
   naturally. Validators that need the full answer (e.g.,
   policy-level "did the model commit to anything risky?")
   should stay on `buffer-then-stream`.
4. **Test against a known leak.** Drive the agent with a
   prompt that should produce a redacted string mid-output
   (e.g., an API key); assert your sentinel never appears in
   any streamed `ChatChunk`.

## Variations

- **Custom boundary regex.** Subclass `ChatSession` and
  override `_make_window_buffer` to tweak the sentence
  segmentation (English `.!?` default).
- **Stream-then-redact (v0.3).** When inline regex redaction
  lands, `stream-then-redact` will skip buffering for
  validators that don't need cross-token context.
- **Multi-language.** Today's segmentation is English-centric;
  CJK / Arabic users should stay on `buffer-then-stream`
  until v0.3 multi-language support ships.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Stream looks delayed | sentence boundaries far apart in long unpunctuated text | the 200-char hard cap fires automatically; check the validator isn't slow |
| Redacted text appears partially | a validator that mutates token-by-token | switch the validator to a sentence-level check |
| `GuardrailViolation` stops the stream | violator surfaced from a per-sentence check | document the policy to the user; surface as a polite refusal chunk |

## Related

- Runbook 11 — Add safety guardrails
- Feature spec: `docs/features/feat-020-chat-agents.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
