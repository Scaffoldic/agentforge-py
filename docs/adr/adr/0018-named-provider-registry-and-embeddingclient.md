# ADR-0018: Named-provider registry + separate `EmbeddingClient` ABC

## Metadata

| Field | Value |
|---|---|
| **Number** | 0018 |
| **Title** | Named-provider registry + separate `EmbeddingClient` ABC |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, providers |

---

## 1. Context and problem statement

Real production agents use multiple LLMs simultaneously: a frontier
model for reasoning, a cheap model as LLM-judge for evaluation, an
embedding model for retrieval, sometimes a vision model and a routing
classifier. Each has its own provider config; each may be from a
different vendor (reasoning on Bedrock, judge on Anthropic).

A single-`model` field on `Agent` only addresses the primary case. And
LLMs and embeddings are different operations — coupling them under one
ABC produces confusing surface ("does `LLMClient.call` do embeddings
when there are no messages?").

How do we model multiple LLMs and embeddings in one agent without
breaking the "swap providers via config" promise?

## 2. Decision drivers

- Production agents need multiple LLMs by role (reasoning, judge,
  embedding, vision)
- Embedding has different inputs (texts, no messages, no tools), outputs
  (vectors), cost model, and providers (Voyage doesn't do chat, Anthropic
  doesn't do embeddings)
- Provider portability — swap via config — must extend to all roles
- Cost cap (ADR-0010) must aggregate across every provider used in a run

## 3. Considered options

1. **Single `model` field on Agent** — only one LLM, embeddings via
   separate untyped imports
2. **Single ABC with `embed` as a capability** — overload `LLMClient`
3. **Named-provider registry + separate `EmbeddingClient` ABC** —
   declare every provider once with a role-name in YAML; reference by
   role across the agent
4. **Multi-`model` keyword arguments** — `Agent(model=, judge_model=,
   embedding_model=)`

## 4. Decision outcome

**Chosen: Option 3 — Named-provider registry + separate
`EmbeddingClient` ABC.**

A new top-level `providers:` block in `agentforge.yaml` declares
every LLM / embedding by role-name (`reasoning`, `fast-judge`,
`embeddings`, `vision`, etc.). The agent and other components reference
providers by role-name: `agent.model: "reasoning"`,
`evaluators.correctness.judge_provider: "fast-judge"`,
`memory.embedding_provider: "embeddings"`.

`LLMClient` (chat) and `EmbeddingClient` (embeddings) are separate ABCs.
A package may register one or both (e.g. `agentforge-openai` registers
both; `agentforge-voyage` registers embedding only).

Inline shorthand (`model: "anthropic:claude-sonnet-4.7"`) still works
for simple agents — both forms coexist.

### Positive consequences

- Multi-LLM agents are first-class
- Cheap-judge / cheap-routing patterns become easy
- Embeddings as separate ABC keeps each surface clean
- Cost aggregates across every provider used in a run

### Negative consequences (trade-offs)

- New top-level `providers:` block to learn
- Two ABCs (LLM + Embedding) instead of one
- Resolver must distinguish "type:model" inline form from "name in
  registry" form (resolved via `:` heuristic)

## 5. Pros and cons of the options

### Option 1: Single `model`

- + Simplest
- − Forces hand-wired secondary LLMs and embeddings

### Option 2: Single ABC with embed capability

- + One contract
- − Conflates two operations; unhelpful default behaviour for embed-only
  providers

### Option 3: Named registry + separate EmbeddingClient (chosen)

- + Multi-LLM is declarative
- + Each ABC has clean semantics
- − One more concept (registry) to learn

### Option 4: Multi-`model` kwargs

- + Easier than registry for simple cases
- − Doesn't scale; every new role needs a new `Agent(...)` kwarg

## 6. References

- ADR-0009 (capability-based LLM client extension)
- [`docs/features/feat-003-llm-provider-abstraction.md`](../features/feat-003-llm-provider-abstraction.md)
- [`docs/features/feat-006-evaluators-and-benchmarks.md`](../features/feat-006-evaluators-and-benchmarks.md) (judge_provider)
