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

## AWS Bedrock (Claude on Bedrock, IAM, assume-role)

Run Claude (or Titan/Cohere embeddings) on **Bedrock** with IAM
credentials instead of an Anthropic API key — the framework `Agent`
runtime, `BudgetPolicy`, retries, and cost/provenance all apply unchanged.

```yaml
providers:
  default:
    type: bedrock
    # Use the INFERENCE-PROFILE id (us./eu./apac./global. prefix).
    # The bare id rejects on-demand throughput with
    #   "… isn't supported. Retry … with an inference profile".
    model: "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    config:
      region: us-east-1
      # Optional: assume an IAM role via STS before calling Bedrock
      # (cross-account / least-privilege). Omit to use the ambient
      # credential chain (env vars, instance profile, IRSA, or an
      # AWS_PROFILE configured with role_arn + source_profile).
      role_arn: "arn:aws:iam::123456789012:role/bedrock-invoke"
agent:
  budget:
    usd: 2.0
```

- **Model id:** the trailing `…-v1:0` is parsed safely — the
  provider/model split is on the *first* `:` only.
- **Credentials:** by default the standard AWS chain is used (env /
  instance profile / IRSA / `AWS_PROFILE`). `role_arn` (+ optional
  `role_session_name`, default `"agentforge"`) performs an explicit STS
  assume-role and drives Bedrock with the temporary credentials.
- **Settings ride the `config:` block.** A plain `agent.model:
  "bedrock:…"` string can only carry the model id; `region` / `role_arn`
  / `aws_profile` / `timeout_seconds` must go under `providers.<name>.config`.
- **Embeddings:** `type: bedrock` also provides Titan / Cohere embeddings
  (`amazon.titan-embed-text-v2:0`, `cohere.embed-english-v3`), with the
  same `region` / `role_arn` config.

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
