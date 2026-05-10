# Configuration-Driven Development

The framework's "Configuration is data, not code" principle (ADR-0013,
P5) extends to **everything**, including tests, fixtures, CI, and
internal thresholds. No magic numbers in code.

## The rule

Every value that might tune for a different deployment, test, or
environment must come from a config file. Hard-coded values in code are
a smell unless the value is mathematically constant.

| Value type | Belongs in | Not in |
|---|---|---|
| Default budget cap (USD) | `pyproject.toml > [tool.agentforge.defaults]` and config schemas | inlined in `Agent.__init__` defaults |
| Test timeout | `tests/fixtures/thresholds.yaml` | `pytest.fixture(timeout=30)` |
| Coverage floor | `pyproject.toml > [tool.coverage]` | inline `--cov-fail-under=90` in scripts |
| Mock LLM responses | `tests/fixtures/llm/<scenario>.jsonl` | inline string literals in test files |
| HTTP server port | `agentforge.yaml > modules.chat_http.port` | hardcoded in `ChatServer.__init__` |
| Provider price tables | shipped per-provider package as YAML | hardcoded in provider client |
| Retry counts | `agentforge.yaml` or per-provider config | constants in retry logic |
| Truncation thresholds | `agentforge.yaml > modules.chat.truncation` | constants in `SlidingWindow` |

## What to do

### Production code

- Constants exposed through Pydantic / Zod config models.
- Defaults live on the model (`field(default=1.0)`); the framework
  never reaches for a hardcoded value.
- Config models are composable — each module ships its own; the root
  schema aggregates.

```python
# Good
class BudgetPolicy(BaseModel):
    usd: float = 1.0
    max_tokens: int = 200_000
    max_iterations: int = 25

class Agent:
    def __init__(self, *, budget: BudgetPolicy = BudgetPolicy(), ...):
        ...

# Bad
class Agent:
    def __init__(self, *, budget_usd: float = 1.0, ...):  # number scattered
        if budget_usd > 100:                              # magic threshold
            ...
```

### Test code

- **Fixtures load from YAML / JSON** under `tests/fixtures/`. Never
  hardcode test inputs as Python literals.
- **Threshold-style values** (timeouts, retry counts, expected counts)
  go in `tests/fixtures/thresholds.yaml` and load via a fixture.
- **Mock LLM scenarios** are JSONL recordings, not inline scripts.

```python
# Good
@pytest.fixture
def thresholds():
    with open("tests/fixtures/thresholds.yaml") as f:
        return yaml.safe_load(f)

async def test_budget_check_blocks_at_cap(thresholds):
    budget = BudgetPolicy(usd=thresholds["budget_test"]["cap_usd"])
    ...

# Bad
async def test_budget_check_blocks_at_cap():
    budget = BudgetPolicy(usd=2.0)   # why 2.0? where does it come from?
    ...
```

### CI / pipeline configuration

- All thresholds (coverage floor, ratchet tolerance, lint severity)
  live in versioned config files.
- Workflow YAML reads from those files; doesn't redeclare values.

## Why this matters at framework level

1. **Tunability.** A team running an agent in their environment may
   need different defaults. If thresholds are baked into code, every
   change requires a fork.
2. **Auditability.** Compliance teams want to see the agent's runtime
   knobs. A config file is auditable; scattered magic numbers are not.
3. **Reproducibility.** Same fixture file, same test result —
   regardless of who runs the suite.
4. **Test honesty.** Hardcoded test inputs hide assumptions. Fixture
   files force you to articulate them.
5. **Upgrade-safety (P8).** When the framework changes a default,
   the change is visible in a config file diff, not buried in a code
   diff.

## Constants that ARE allowed in code

These are mathematical or protocol-level constants, not tunables:

- `SECONDS_PER_MINUTE = 60` — a unit conversion
- HTTP status codes (`200`, `404`) — protocol-defined
- Bit masks, enum values — language constructs
- Algorithmic constants where the algorithm is named in the code
  (`GOLDEN_RATIO = 1.618...`)

If the value might ever sensibly take another number, it's a tunable —
it goes in config.

## Pre-commit enforcement

`scripts/check_no_magic_numbers.py` (ships with feat-001) scans for:

- Numeric literals in production code that aren't 0, 1, or in a list
  of allowed math constants
- String paths that look like file paths in production code
- Sleep / timeout / retry counts inline anywhere

The check is pragmatic — false positives can be silenced via inline
comment `# config-exempt: <reason>`. Reviewer must accept the
justification.

## References

- ADR-0013 (configuration is data, not code)
- [`docs/design/design-principles.md`](../../docs/design/design-principles.md) — P5
- [`docs/features/feat-012-configuration-system.md`](../../docs/features/feat-012-configuration-system.md)
- [`.claude/standards/testing.md`](./testing.md) — fixtures discipline
