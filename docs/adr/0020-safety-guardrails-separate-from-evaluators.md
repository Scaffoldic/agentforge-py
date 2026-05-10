# ADR-0020: Safety guardrails as a separate feature with three ABCs (vs evaluators)

## Metadata

| Field | Value |
|---|---|
| **Number** | 0020 |
| **Title** | Safety guardrails as a separate feature with three ABCs (vs evaluators) |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, security |

---

## 1. Context and problem statement

Production agents face two related but distinct concerns:

- **Real-time defenses**: prompt injection, PII leakage, jailbreak
  detection, tool-call authorization. These must *block or redact at
  the moment* a violation happens.
- **Quality scoring**: faithfulness, groundedness, hallucination,
  correctness, helpfulness. These run *post-run* and produce scores
  that inform CI gates and dashboards.

A naive design conflates them ("an evaluator that scores PII-leak rate
*and* blocks it"). That confusion produces evaluators that have to fire
synchronously (latency cost on every turn) and policy that lives in the
wrong place.

How do we separate the two concerns at the contract layer so each can
evolve cleanly?

## 2. Decision drivers

- Real-time blocking and post-run scoring have different semantics
  (synchronous vs asynchronous, decision vs measurement)
- Each has its own module ecosystem (LLM Guard, Presidio, NeMo,
  Llama Guard for guardrails; Ragas, DeepEval, G-Eval for evaluation)
- Lifecycle integration points differ (before/after LLM, before tool
  vs end of run)
- Defaults-on policy (P6) for safety must not couple to defaults-on for
  evaluators (which are off by default — they cost money)

## 3. Considered options

1. **Single `Evaluator` ABC** — score and gate are the same thing; the
   `action: "block" | "redact" | "score"` field decides
2. **Two ABCs** — `Evaluator` (score) + one general `Guardrail` ABC
3. **Two features, four ABCs** — `Evaluator` (score, post-run) +
   `InputValidator` / `OutputValidator` / `ToolCallGate` (block/redact,
   real-time)
4. **External proxy** — guardrails as a separate process / sidecar

## 4. Decision outcome

**Chosen: Option 3 — Two features, four ABCs.**

feat-006 owns `Evaluator` (post-run scoring; deterministic graders +
LLM-judge; cost-bounded by remaining budget). feat-018 owns
`InputValidator` (before LLM), `OutputValidator` (after LLM),
`ToolCallGate` (before tool dispatch) — three ABCs because their
inputs and lifecycle points differ. Defaults are loud for safety
(basic prompt-injection regex + PII redaction + tool capability
gates auto-on); evaluators are off by default.

PII and toxicity overlap both concerns: as gates (real-time block /
redact) they live in feat-018; as metrics (how often does this agent
leak?) they live in feat-006. Both can run on the same agent; the
features are explicitly designed to coexist.

### Positive consequences

- Each ABC's semantics are crisp
- Module ecosystems map cleanly (Presidio = guardrail; G-Eval =
  evaluator)
- Defaults policy works per-feature without surprises
- Future evolution doesn't entangle the two concerns

### Negative consequences (trade-offs)

- Four ABCs (Evaluator + 3 guardrails) instead of one
- Documentation must repeatedly clarify the distinction (covered in
  feat-006 §4.2 with explicit boundary text)
- Some users will want a unified API; we say no and explain

## 5. Pros and cons of the options

### Option 1: Single `Evaluator`

- + One concept
- − Conflates synchronous gating with asynchronous scoring
- − Latency cost forced on every turn for what should be post-run

### Option 2: Two ABCs

- + Cleaner than option 1
- − One Guardrail ABC isn't enough — input/output/tool-call have
  different signatures and lifecycle points

### Option 3: Two features, four ABCs (chosen)

- + Crisp, lifecycle-correct
- + Module ecosystems map naturally
- − More ABCs to learn

### Option 4: External proxy

- + Clean separation
- − Adds infra; doesn't help in-process agents
- − Real-time blocking via a proxy adds another network hop

## 6. References

- [`docs/features/feat-006-evaluators-and-benchmarks.md`](../features/feat-006-evaluators-and-benchmarks.md)
- [`docs/features/feat-018-safety-and-security-guardrails.md`](../features/feat-018-safety-and-security-guardrails.md)
- [`docs/design/architecture.md`](../design/architecture.md) §3 (Evaluator vs Validator distinction)
- OWASP LLM Top 10
