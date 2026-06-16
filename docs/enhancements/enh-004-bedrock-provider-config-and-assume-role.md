# enh-004: provider `config:` passthrough + Bedrock STS assume-role

> Improves a *shipped* feature (feat-003, LLM provider abstraction). Filed
> as issue #92 by a consumer agent running Claude + Cohere on AWS Bedrock.
> The Bedrock provider already exists and is published; the real gaps are
> (1) `providers.*.config` was documented but silently dropped, so AWS
> settings could not reach the client via YAML, and (2) no first-class STS
> assume-role for cross-account / least-privilege Bedrock access.

---

## Metadata

| Field | Value |
|---|---|
| **ID** | enh-004 |
| **Title** | Pass `providers.config` to the provider constructor + Bedrock `role_arn` assume-role |
| **Status** | `shipped` (0.5.0) |
| **Owner** | kjoshi |
| **Created** | 2026-06-16 |
| **Target version** | 0.5.0 |
| **Languages** | `python` |
| **Improves** | feat-003 (LLM provider abstraction) |

---

## 1. Summary

Honor the `providers.<name>.config` block (already in the schema, already
documented in runbook 13) by passing it to the provider constructor, so
`region` / `aws_profile` / `role_arn` / `timeout_seconds` reach the client
from YAML. Add a `role_arn` (+ `role_session_name`) option to the Bedrock
chat and embedding clients that performs an STS assume-role before driving
`bedrock-runtime`.

## 2. Motivation

Issue #92 reported "there is no AWS Bedrock provider." In fact
`agentforge-bedrock` is published (PyPI 0.2.x) and registered — `BedrockClient`
(Converse, tools, streaming, retry, pricing, inference-profile ids) and
`BedrockEmbeddingClient` (Titan/Cohere) both work. The consumer re-rolled
boto3 because two things blocked configuring it:

1. **`providers.config` was dropped.** `ProviderConfig.config` is documented
   ("passed through to the provider's constructor") and runbook 13 shows a
   `config:` block — but `_resolve_llm` collapsed the named provider to a
   bare `"type:model"` string, discarding `config`. So **no** provider
   (Bedrock, Anthropic, OpenAI) could receive `region` / credentials / retry
   settings from YAML; the only path was constructing the client in Python
   and passing the instance.
2. **No first-class assume-role.** Bedrock in production is commonly reached
   via an assumed IAM role (cross-account, least-privilege). The ambient
   chain (`AWS_PROFILE` with `role_arn`, IRSA, instance profile) works, but
   there was no explicit per-client `role_arn`.

The inference-profile gotcha the issue calls out (`us.anthropic.claude-…`,
the `…-v1:0` suffix) is **already handled** — documented here and in runbook
13 so it stops surprising people.

## 2.5 Framework-level vs derived-agent-level

**Framework.** Provider construction from config and the AWS session/STS
wiring are framework code. A consumer cannot make `providers.config` work
(the build path owns it) and shouldn't re-implement STS credential plumbing
per agent.

- **Derived-agent test:** the workaround (call `bedrock-runtime` via boto3
  directly, reuse only the `BudgetPolicy` value) re-implements the runtime
  the framework owns — fails the test → framework work.
- **How it helps derived agents:** an AWS agent configures Bedrock entirely
  in YAML (`type: bedrock`, inference-profile `model`, `region`, `role_arn`)
  and gets the `Agent` runtime + budget + provenance + retry/pricing — one
  IAM credential set, swap-by-config between the Anthropic API and Bedrock.

## 3. Before / after

| Aspect | Before | After |
|---|---|---|
| `providers.default.config` | silently dropped | passed to the provider constructor |
| Region / creds from YAML | impossible (Python construction only) | `providers.<name>.config: { region, aws_profile, … }` |
| Bedrock assume-role | ambient chain only | explicit `role_arn` (+ `role_session_name`) via STS |
| Inference-profile id | worked, undocumented | documented (runbook 13) |

## 4. Backward compatibility

Additive. A provider with no `config:` block still resolves to the same
`"type:model"` string. A config key the provider can't accept raises a clear
`ModuleError` (was: silently ignored). `role_arn=None` (default) keeps the
ambient credential chain — no behaviour change for existing Bedrock users.

## 5. Implementation

- `_resolve_llm` (`agentforge/cli/_build.py`): when `providers.default.config`
  is non-empty, build the client via the resolver with
  `cls(model_id=…, **config)` (the same `cls(model_id=…)` contract `Agent`
  uses for a model string, extended with the settings); a `TypeError` from
  unknown keys surfaces as a `ModuleError`.
- `BedrockClient` / `BedrockEmbeddingClient`: new `role_arn` /
  `role_session_name` params. `_ensure_client` calls a new
  `_assume_role_credentials()` (STS `assume_role` → temp credential kwargs)
  when `role_arn` is set, else uses the ambient session.

## 6. Test plan

- `test_provider_config_block_passed_to_constructor` — a recording fake
  provider receives `model_id` + the `config` kwargs.
- `test_provider_config_rejects_unknown_keys` — unknown key → `ModuleError`.
- `test_assume_role_drives_bedrock_with_temp_credentials` /
  `test_embedding_assume_role_drives_runtime_with_temp_credentials` — an
  injected session asserts STS `assume_role` is called and the temp
  credentials are threaded into the `bedrock-runtime` client; the no-role
  path skips STS.

## 7. Out of scope (backlog)

- **`config:` on a plain `agent.model` string.** Settings still require the
  `providers.<name>` form; attaching config to a bare `agent.model: "…"`
  string is deferred.
- **Generic "model-role" registry** (judge / summarizer / classifier as
  `provider:model`) from the issue's "related" list — its own feat.

## 8. References

- Improved feature: feat-003 (LLM provider abstraction)
- Issue: #92
- Runbook: 13 — Configure multi-provider (AWS Bedrock section)
