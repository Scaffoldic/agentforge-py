---
status: open
severity: P2 (testing-coverage gap, not a code defect)
found-in: surfaced by bug-009 (2026-05-27)
found-via: post-fix retro
---

# bug-011 — No provider conformance harness; payload-shape bugs invisible to unit tests

## Symptom

Bug-009 (ReAct dropped `response.tool_calls` when re-feeding the
assistant turn) shipped in v0.2.3 with a fully green unit suite. The
real Bedrock Converse validator rejected every tool-using prompt on
the first call once `a downstream consumer` integrated the library — but
no test in the workspace ever exercised that path end-to-end.

## Root cause

- Every provider package's tests use fake clients
  (`_FakeBedrockClient`, `FakeOpenAIRunner`, `FakeAnthropicRunner`)
  that accept ANY payload shape. The framework's
  `_build_converse_request` / `_message_to_<provider>` can produce
  invalid payloads and the fakes happily return canned responses.
- No test in the workspace exercises a multi-iteration ReAct round-
  trip against a real provider — even via a recorded cassette.

## Impact

Any future bug whose symptom only surfaces at the provider's
request validator (orphaned tool blocks, missing required fields,
malformed enum values, payload-size limits, etc.) will ship to
adopters before we see it. Bug-009 is the first confirmed instance.

## Fix proposal (v0.3 backlog)

Add a cassette-based conformance harness. Sketch:

1. New test directory per provider package:
   `tests/conformance/`. Use `pytest-recording` (or `vcrpy` directly)
   to record one live multi-iteration tool round-trip per provider
   against a real account. Recordings live in
   `tests/conformance/cassettes/`.
2. CI replays cassettes only — never re-records. Recording is a
   manual maintainer task (`pytest --record-mode=rewrite` against
   real creds) when a provider's wire format changes.
3. Auth scrubbing: cassettes redact `Authorization`,
   `x-api-key`, `x-amz-security-token`, and any account-id-shaped
   query params before commit. Centralise the scrub list in a
   shared `conftest.py`.
4. Decisions deferred until implementation: per-package cassettes
   vs. workspace-wide fixture directory; re-record cadence
   (per-release vs. per-quarter); whether to also conform the
   streaming paths (yes, but separate cassette).

## Notes

- Linked from bug-009 §Notes — that's the motivating incident.
- This is a testing-coverage gap, not a code defect. No production
  fix required; the deliverable is test infra + at least one
  recorded round-trip per provider (bedrock, openai, anthropic).
- v0.3 roadmap entry should reference this doc.
- Should land BEFORE the v0.3.0 cut so we don't carry the same
  blind spot into the TypeScript port (feat-024 / v0.4).
