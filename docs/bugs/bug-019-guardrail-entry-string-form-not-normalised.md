---
status: fixed in 0.2.4
severity: P2
found-in: v0.2.3
found-via: live integration of a Bedrock-backed MCP agent (Khemchand Joshi, 2026-05-27)
---

# bug-019 — `GuardrailEntry` string-form in YAML doesn't auto-normalise to `{name: ...}` despite docstring

## Symptom

The `GuardrailEntry` schema's docstring (`agentforge_core/config/schema.py`)
documents two YAML shapes:

> Two YAML shapes are valid (mirrors `EvaluatorEntry`):
> - String form: `- prompt_injection_basic` (just the name).
> - Mapping form: `- presidio: {entities: ["EMAIL_ADDRESS"]}`.
>
> Both normalise to `GuardrailEntry(name=..., config={})` before validation.

The string form fails validation:

```yaml
modules:
  guardrails:
    tool_gates:
      - my_role_gate   # ← string form, per docstring
```

```
agentforge.yaml validation failed:
  modules.guardrails.tool_gates.0: Input should be a valid dictionary
  or instance of GuardrailEntry
```

## Reproduction

```yaml
# agentforge.yaml — minimal repro
modules:
  guardrails:
    tool_gates:
      - capability_check        # framework-shipped name
```

```
$ agentforge config validate
agentforge.yaml validation failed:
  modules.guardrails.tool_gates.0: Input should be a valid dictionary
  or instance of GuardrailEntry
```

## Root cause

The promised string→mapping normaliser isn't wired anywhere — not on
the `GuardrailEntry` field's `before` validator and not in the loader's
pre-parse step (`loader.py:203-207` runs env interpolation then
`model_validate` directly; both `GuardrailEntry` and `EvaluatorEntry` are
`strict=True, extra="forbid"`).

**Scope is wider than first reported — verified 2026-06-02.** The
original draft guessed that `EvaluatorEntry` "may suffer the same gap."
It does — `EvaluatorEntry` is **equally broken**, not a working
reference. Three docstrings promise a string form that all fail
validation:

- `GuardrailEntry` docstring (`schema.py:226-236`)
- `EvaluatorEntry` docstring (`schema.py:180-188`) — explicitly attributes
  normalisation to "the loader", which does no such thing
- the `ModulesConfig` / `GuardrailsConfig` example YAML
  (`schema.py:369,372-374`), e.g. `evaluators: [faithfulness]` and
  `input: [prompt_injection_basic]` — both fail

So the single fix must cover `modules.evaluators` **and** guardrails'
`input` / `output` / `tool_gates`.

## Fix proposal

Add a `field_validator(..., mode="before")` (or `model_validator`) on
the parent container that converts `str` items into `{"name": str}`
dicts before Pydantic strict validation runs:

```python
@field_validator("tool_gates", mode="before")
@classmethod
def _normalise_string_entries(cls, v: Any) -> Any:
    if isinstance(v, list):
        return [{"name": item} if isinstance(item, str) else item for item in v]
    return v
```

Mirror to `input`, `output`, `tool_gates` lists and to
`modules.evaluators`.

## Workaround

Use the mapping form everywhere:

```yaml
tool_gates:
  - name: my_role_gate
```

Consumers use this form.

## Framework-level vs derived-agent-level

**Framework.** The schemas, their docstrings, the documented example
YAML, and the loader are all `agentforge-core`. The framework documents
a config syntax (in three places) that its own loader and `strict=True`
models reject.

- **Derived-agent test:** the consumer can use the mapping form as a
  workaround, but the bug is that the framework *documents* the string
  form and then rejects it — a doc-vs-code contradiction the consumer
  can't fix. Framework defect.
- **How the fix helps derived agents:** the documented terse syntax
  (`- prompt_injection_basic`, `- faithfulness`) actually works, so
  copy-pasting from the docstrings/examples doesn't produce a
  `ValidationError`. Config ergonomics the docs already promise.

## Notes

- Low severity (P2): workaround is trivial and the error is specific. But
  the fix should normalise (not just delete the docstring promise), since
  the terse form appears in shipped example YAML across three configs.
  Implement the `mode="before"` normaliser once and mirror it to
  `evaluators`, `input`, `output`, `tool_gates`.

## Resolution (v0.2.4)

Implemented as a single shared helper `_normalise_named_entry` plus a
`@model_validator(mode="before")` on **both** `EvaluatorEntry` and
`GuardrailEntry` (`agentforge_core/config/schema.py`). Putting the
normaliser on the entry models rather than on each parent list means one
validator per type covers every usage — `modules.evaluators` and
guardrails' `input` / `output` / `tool_gates` — with no per-field
duplication, and it composes through Pydantic's list validation even
under `strict=True`.

Scope was wider than the reported string-form symptom: the **single-key
mapping sugar** (`- geval: {rubric: ...}`, shipped in the schema's own
example YAML) was equally broken under `extra="forbid"`. The fix
normalises all three documented shapes — string, single-key mapping, and
canonical `{name, config}` — so copy-pasting any of them validates.
Docstrings for both entries were corrected (they claimed "the loader
normalises"; the loader does not — it is now the entry's before-validator).
`ObservabilityEntry` shares the shape but its docs/example only show the
canonical form, so it is intentionally left unchanged (no doc-vs-code
contradiction to fix). Tests cover all three forms across evaluators +
all three guardrail gates, plus empty-name rejection and that canonical
dicts still forbid extra keys.
