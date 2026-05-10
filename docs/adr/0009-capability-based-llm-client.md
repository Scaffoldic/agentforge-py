# ADR-0009: Capability-based LLM client extension

## Metadata

| Field | Value |
|---|---|
| **Number** | 0009 |
| **Title** | Capability-based LLM client extension |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, providers |

---

## 1. Context and problem statement

LLM providers ship features at different times: Anthropic has prompt
caching and extended thinking; OpenAI has parallel tool calls and JSON
mode; Bedrock has neither caching nor thinking yet. A framework
abstraction that exposes only the lowest common denominator (basic
`call()`) leaves capability features unused; one that requires every
provider to implement every method forces fakes everywhere.

How do we expose provider-specific capabilities while keeping the
abstraction stable and provider-portable?

## 2. Decision drivers

- Per-feature ROI is real (caching cuts cost 50–90% on big static
  prefixes; extended thinking improves hard reasoning)
- Provider portability must be preserved — agents that don't need a
  capability shouldn't depend on it
- Capability negotiation must be testable
- LCD (lowest-common-denominator) APIs are a known anti-pattern

## 3. Considered options

1. **LCD `call()` only** — only one method on the abstraction
2. **Capability methods + `capabilities()` introspection** —
   `LLMClient` exposes optional methods (`call_with_cache`,
   `call_with_thinking`, `stream`); each provider declares which it
   actually implements
3. **Provider-specific subclasses** — `AnthropicLLMClient` exposes
   Anthropic-only methods; consumers reach for the typed class
4. **Generic `call(extras={"caching": ...})`** — overload the basic
   call with an open dict of extras

## 4. Decision outcome

**Chosen: Option 2 — Capability methods + `capabilities()` introspection.**

`LLMClient` requires `call()` and `close()`. It additionally exposes
optional methods (`call_with_cache`, `call_with_thinking`, `stream`)
that default to `NotImplementedError` and are overridden by providers
that support the feature. Every provider declares its set of supported
capabilities via `capabilities() -> set[str]`. Consumers (strategies,
the Agent) check before using:

```python
if llm.supports("caching") and prefix_size > threshold:
    response = await llm.call_with_cache(...)
else:
    response = await llm.call(...)
```

A nightly conformance test verifies: a provider's *declared* capabilities
actually work against the real SDK — declared caps are honest.

### Positive consequences

- Provider-specific features are reachable without leaking provider types
- Agents that don't need a capability don't depend on it
- Adding a capability is additive — non-supporting providers continue to
  work
- Capability flag set is small and closed (`caching`, `thinking`,
  `streaming`, `tools`, `json_mode`, `vision`, `parallel_tools`)

### Negative consequences (trade-offs)

- `LLMClient` ABC has more methods than the strict minimum
- Each provider must declare its set honestly — enforced by conformance
- Capability set evolves over time — every new addition requires a
  feature doc

## 5. Pros and cons of the options

### Option 1: LCD only

- + Simplest abstraction
- − Caching, thinking, streaming all unreachable

### Option 2: Capability + introspection (chosen)

- + Capability-rich without losing portability
- + Honest negotiation; consumers can branch
- − Slightly larger ABC surface

### Option 3: Provider subclasses

- + Direct typed access
- − Defeats portability; agents now depend on `AnthropicLLMClient`

### Option 4: Generic `extras` dict

- + Minimal surface
- − Untyped; bug-prone; no autocomplete

## 6. References

- ADR-0007 (ABC + Protocol surface)
- ADR-0018 (Named-provider registry + `EmbeddingClient`)
- [`docs/features/feat-003-llm-provider-abstraction.md`](../features/feat-003-llm-provider-abstraction.md)
- Archived: `docs/archive/cr/CR-005b-coverage-ratchet-and-capability-llm.md`
