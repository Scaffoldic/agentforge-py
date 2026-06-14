# Architecture Decision Records

Every load-bearing architectural decision in AgentForge is captured as an
immutable ADR. ADRs use the **MADR (Markdown ADR) format** — a modern
extension of Michael Nygard's original ADR template, compatible with the
arc42 documentation standard (§9 Architecture Decisions).

> **Why ADRs.** The framework will outlive the people who designed it.
> ADRs preserve the *why* of every choice. Future contributors who want
> to challenge a decision can read the context, the alternatives, and the
> drivers that led here — and either confirm the decision still holds or
> propose a superseding ADR.

## Format

ADRs are numbered with 4-digit zero-padded ids (`0001`, `0002`, ...) so
they sort lexicographically. Numbers are **immutable** — once assigned,
never reused. An ADR that no longer reflects current practice is marked
**Superseded by ADR-NNNN** and stays in place; the superseding ADR
references the original.

Template: [`/.claude/templates/adr.md`](../../.claude/templates/adr.md).

## Status legend

| Status | Meaning |
|---|---|
| **Proposed** | Drafted, awaiting acceptance |
| **Accepted** | Active — describes current architecture |
| **Superseded by ADR-NNNN** | Replaced; kept for history |
| **Deprecated** | No longer relevant; not yet superseded by a specific ADR |

## Index

| # | Title | Status | Tags |
|---|---|---|---|
| [0001](./0001-framework-name-agentforge.md) | Framework name — AgentForge | Accepted | brand, naming |
| [0002](./0002-multi-language-python-typescript.md) | Multi-language: Python and TypeScript with contract parity | Accepted | architecture, scope |
| [0003](./0003-three-tier-package-model.md) | Three-tier package model (core / runtime / modules) | Accepted | architecture, packaging |
| [0004](./0004-module-discovery-via-entry-points.md) | Module discovery via Python entry points / npm exports | Accepted | architecture, modules |
| [0005](./0005-copier-not-cookiecutter-for-scaffolding.md) | Copier (not Cookiecutter) for scaffolding and upgrades | Accepted | scaffolding, upgrade |
| [0006](./0006-marker-header-file-ownership.md) | Marker-header file ownership (managed / forked / owned) | Accepted | scaffolding, upgrade |
| [0007](./0007-abc-protocol-as-stable-surface.md) | ABC + Protocol contracts as the framework's stable surface | Accepted | architecture, contracts |
| [0008](./0008-pluggable-reasoning-strategy.md) | Pluggable reasoning strategy ABC | Accepted | architecture, reasoning |
| [0009](./0009-capability-based-llm-client.md) | Capability-based LLM client extension | Accepted | architecture, providers |
| [0010](./0010-production-rails-framework-owned.md) | Production rails (cost, run_id, fallback, idempotency) framework-owned | Accepted | architecture, production |
| [0011](./0011-memorystore-abc-and-driver-set.md) | Single MemoryStore ABC + optional GraphStore + 4 drivers | Accepted | architecture, persistence |
| [0012](./0012-finding-as-protocol-with-variants.md) | `Finding` as Protocol with shipped variants (not a single dataclass) | Accepted | architecture, output |
| [0013](./0013-configuration-is-data-not-code.md) | Configuration is declarative data (not Turing-complete) | Accepted | architecture, config |
| [0014](./0014-async-first-core.md) | Async-first core in both languages | Accepted | architecture, concurrency |
| [0015](./0015-coordinated-release-train.md) | Coordinated release train across all packages | Accepted | release-engineering |
| [0016](./0016-apache-2-license.md) | Apache 2.0 license | Accepted | licensing, governance |
| [0017](./0017-agents-md-as-canonical-ai-rules.md) | `AGENTS.md` as canonical AI-assistant rules file | Accepted | dx, ai-tooling |
| [0018](./0018-named-provider-registry-and-embeddingclient.md) | Named-provider registry + separate `EmbeddingClient` ABC | Accepted | architecture, providers |
| [0019](./0019-chatsession-as-wrapper-over-agent.md) | `ChatSession` as wrapper over `Agent` (not a new class) | Accepted | architecture, deployment |
| [0020](./0020-safety-guardrails-separate-from-legacyluators.md) | Safety guardrails as a separate feature with three ABCs (vs evaluators) | Accepted | architecture, security |
| [0021](./0021-native-typescript-scaffolding-engine.md) | Native TypeScript scaffolding engine (companion to ADR-0005) | Accepted | scaffolding, upgrade, typescript |
| [0022](./0022-app-passthrough-for-application-config.md) | Reserved `app:` block for application config in `agentforge.yaml` | Accepted | architecture, config |

## Process

- New ADR: copy the template, pick the next number, fill every section,
  set status to `Proposed`. Open a PR.
- Reviewing an ADR: focus on context and decision drivers; the chosen
  option is fine if the alternatives are honestly considered.
- Superseding an ADR: write a new ADR explaining what changed and why;
  edit the old one's status line to `Superseded by ADR-NNNN`. Do not
  delete the old ADR; do not edit its body beyond the status field.
- Deprecating without replacement: mark the old ADR `Deprecated` and
  state in the metadata block why no replacement is needed.

## References

- Michael Nygard — *Documenting Architecture Decisions* (2011): https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- MADR (Markdown ADR) v3: https://adr.github.io/madr/
- arc42 §9 Architecture Decisions: https://docs.arc42.org/section-9/
- ADR community index: https://adr.github.io/
