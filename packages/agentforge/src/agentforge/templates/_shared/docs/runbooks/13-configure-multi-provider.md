# 13 — Configure multi-provider

> **Goal:** run different model classes for reasoning, judging,
> and embedding without rewriting your agent.
> **Time:** ~10 minutes.
> **Prereqs:** runbook 01.

## TL;DR

```yaml
# agentforge.yaml
providers:
  default:
    type: anthropic                                    # native Anthropic API
    model: claude-sonnet-4-7
  judge:
    type: anthropic
    model: claude-haiku-4-5                            # cheaper judge
  embed:
    type: voyage
    model: voyage-3-large
agent:
  model: anthropic:claude-sonnet-4-7
modules:
  evaluators:
    - name: faithfulness
      config:
        judge_provider: judge
```

**Available provider drivers (v0.2):**

| `type:` | Package | Capabilities |
|---|---|---|
| `bedrock` | `agentforge-bedrock` | tools, json_mode, caching, thinking, streaming |
| `anthropic` | `agentforge-anthropic` | tools, json_mode, caching, thinking, streaming |
| `openai` | `agentforge-openai` | tools, json_mode, streaming, vision (gpt-4o*) |
| `ollama` | `agentforge-ollama` | tools, streaming (local; zero cost) |
| `litellm` | `agentforge-litellm` | tools (router → 100+ backends) |
| `voyage` | `agentforge-voyage` | embedding-only; matryoshka |

## Step by step

1. **Name your providers** under the top-level `providers:` map.
   `default` is the one `agent.model` falls back to; named
   entries (`judge`, `embed`, `summariser`) can be addressed by
   downstream modules.
2. **Pick the reasoning model.** `agent.model` is the agent's
   primary LLM. Use the strongest model you can afford.
3. **Use a cheaper judge** for LLM-judge evaluators. Per
   feat-006, judge graders take a `judge_provider` config that
   resolves the named provider. Cheap haiku-class models bring
   judge cost down 10x with marginal quality loss for boolean
   evaluations.
4. **Separate embedding from reasoning.** Vector indexing
   typically benefits from a dedicated embedder
   (`voyage-3`, `text-embedding-3-large`). Wire it into
   `modules.retriever.embedding_provider`.
5. **Per-module overrides.** Any module that takes an LLM (
   guardrails / evaluators / etc.) can name a provider.

## Variations

- **Fallback chain.** Use `agentforge_core.production.FallbackChain`
  to wrap two providers; primary first, secondary on
  `RateLimitError` / `ServiceError`.
- **Different providers per environment.** `agentforge.dev.yaml`
  overlay points at a cheap dev model; `agentforge.prod.yaml`
  swaps to the production tier. `AGENTFORGE_ENV=prod` selects.
- **Mock provider for tests.** Register `MockLLMClient` as a
  named provider so config-driven tests reuse it.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No LLM provider registered for X` | provider package not installed | `agentforge add module <X>` |
| Judge cost > reasoning cost | judge running on the same big model | name a cheaper judge provider |
| Embedder shape mismatch | mixed-dimension stores | pin embedding model + dimension in the vector store config |
| Run intermittently 5xx | provider outage | wrap with FallbackChain |

## Related

- Runbook 10 — Add evaluators (judge_provider)
- Runbook 14 — Deploy your agent (environment overlays)
- Feature spec: `docs/features/feat-003-llm-provider-abstraction.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
