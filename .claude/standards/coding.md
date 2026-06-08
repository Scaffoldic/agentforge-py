# Coding Standards

Strict standards. Pre-commit blocks violations. The framework's
production-ready promise (P3, P4, P11) starts here.

## Python (`python/agentforge-py/` and any Py module package)

### Language and runtime

- Python **3.13** minimum (as of 2026-05-09). Use the latest stable
  language features. Older versions not supported.
- Standard library first; third-party only when justified (record the
  justification in the feature doc).

### Library adoption — deep-dive before depending

Before adding any third-party library to a `pyproject.toml`:

1. **Read the library's recommended-usage docs end-to-end.** Not blog
   posts. The official docs.
2. **Confirm we're using its idiomatic patterns.** A library used
   "wrong" is worse than a hand-rolled implementation.
3. **Check release cadence and maintenance status.** Stale or
   abandoned libraries are net-negative.
4. **Check security history.** CVEs, published advisories.
5. **Document the justification** in the feature doc that introduces
   the dep — what library, why, which alternatives considered.

The same rule applies to TypeScript packages.

This is non-negotiable: `pip install` / `pnpm add` of an unfamiliar
library and then learning it as you write code produces sub-par
implementations that have to be re-done. Read first, code second.

### Static analysis

- **`ruff`** — formatter (replaces `black`) + linter (replaces `flake8`,
  `isort`, `pylint`). Config: `pyproject.toml > [tool.ruff]`.
- **`mypy --strict`** — type checking. Strict mode mandatory. Config:
  `pyproject.toml > [tool.mypy]`.
- **`bandit`** for security linting on production code.
- All three run in pre-commit; failures block the commit.

### Type hints

- **Every** public function, method, attribute is typed.
- Use PEP 604 unions: `int | None`, not `Optional[int]`.
- `Any` only at genuine boundary (raw provider responses); never used to
  paper over untyped internals.
- Generics where they add safety: `dict[str, Tool]`, `list[Finding]`.
- Type aliases for reused complex shapes:
  `JSONValue: TypeAlias = ...`.

### Models and data

- **Pydantic v2** for every value type, config schema, public input/output.
  No bare dataclasses for public surface. (Internal-only value types may
  use `@dataclass(frozen=True, slots=True)` for performance.)
- Validators on input boundaries; `model_config = ConfigDict(frozen=True)`
  for immutable types.
- Discriminated unions for variant types: `Annotated[..., Field(discriminator="kind")]`.

### Async

- **All public methods on contracts are `async def`** (per ADR-0014).
- `asyncio.TaskGroup` (Python 3.11+) for structured concurrency.
- Never call `asyncio.run()` inside library code; reserved for CLI
  entry points and the `*_sync` shims.
- Sync tools wrapped in `asyncio.to_thread` automatically by the
  framework; document the perf cost.

### Logging

- **Never use `print()`** in library code.
- Use `logging.getLogger(__name__)`. Never module-level `logging.info(...)`.
- `RunIdFilter` (per feat-007) is auto-attached; never reach for a
  custom correlation id.
- Log levels: `DEBUG` for detail, `INFO` for milestones, `WARNING` for
  recoverable issues, `ERROR` for unrecoverable. Never log secrets or
  full prompts at INFO+.

### Errors

- Define explicit exception classes per module: `BudgetExceeded`,
  `ProviderError`, `GuardrailViolation`, etc. No `raise Exception(...)`.
- Catch narrowly. Never `except Exception` outside of a clearly-bounded
  retry / fallback layer.
- Never swallow exceptions to "make the agent more robust" — let them
  surface; the framework records them as observations and the LLM
  recovers.

### Comments and docstrings

- Default to writing **no comments**. Only when the *why* is non-obvious
  (a hidden constraint, a workaround for a specific bug, behaviour that
  would surprise a reader).
- Public API docstrings only. Format: Google style, single-paragraph
  summary; details in the feature doc.
- Never reference the current task or PR in code comments. That belongs
  in the commit message and feature doc.
- Never write multi-paragraph docstrings or multi-line comment blocks.

### Imports

- Absolute imports inside the framework: `from agentforge.tools import web_search`.
- Relative imports only inside a single package's internals when there
  is a meaningful internal hierarchy.
- Group: stdlib, third-party, framework, local. Sorted by `ruff isort`.

### Naming

- Classes: `PascalCase` (`AgentForgeConfig`, `ChatSession`).
- Functions / methods / variables: `snake_case`.
- Module-level constants: `UPPER_SNAKE_CASE`.
- Private: `_leading_underscore` for module-private; `__double_leading`
  reserved for name-mangling (rarely needed).

### Forbidden patterns (anti-patterns)

- **Importing another agent framework's primitives** anywhere in this
  codebase. Wrong framework.
- **Hand-written JSON schemas** for tools. Use type hints + the
  `@tool` decorator.
- **Dynamic imports of arbitrary paths** from config files.
- **API keys as YAML literals.** Always `${ENV_VAR}`.
- **Wrappers around `Agent.run()` to add cross-cutting features.** Use
  hooks (feat-009).
- **Module-level singleton config** (`dspy.configure(...)` style). Use DI.
- **Threading** for I/O. Use `asyncio`.

---

## TypeScript (`ts/agentforge-ts/` and any TS module package)

### Language and runtime

- TypeScript **5.x** with `strict: true`.
- Node **20+** as runtime target; ESM only.
- `package.json > "type": "module"` everywhere.

### Static analysis

- **`biome`** — formatter + linter (single tool replacing
  prettier+eslint). Config: `biome.json`.
- `tsc --noEmit` for type checking.
- Both run in pre-commit; failures block.

### Types

- Strict: `noImplicitAny`, `strictNullChecks`, `noUncheckedIndexedAccess`,
  `exactOptionalPropertyTypes`.
- `unknown` at boundaries; `any` forbidden in production code.
- Discriminated unions for variants: `kind: "patch"` etc.

### Models and data

- **`zod`** for runtime validation at the seam (config files, HTTP
  inputs, LLM responses).
- Internal-only types are TS interfaces / types — no runtime cost.

### Async

- Native promises and `async/await`. No `then()` chains in new code.
- `AbortController` + `AbortSignal` for cancellation throughout.
- `AsyncLocalStorage` for `run_id` propagation (the TS equivalent of
  Python's `ContextVar` per ADR-0010).

### Imports

- ESM only: `import { x } from "./foo.js"` (note `.js` extension on
  source paths even when the source is `.ts`).
- Sorted by biome.

### Naming

- Same as Python equivalents adjusted for TS idiom: `PascalCase` for
  types/classes, `camelCase` for functions/variables, `UPPER_SNAKE_CASE`
  for module constants.

---

## Both languages

### Function size and complexity

- A function over **40 lines** of body is suspect.
- Cyclomatic complexity over **10** is suspect.
- Both surface as ruff / biome warnings; not auto-fail, but reviewer
  must justify.

### File organisation

- One **public** class per file when the class is non-trivial.
  Private helpers may share a file.
- Files mirror the package's public structure: `agent.py` exports `Agent`,
  `agent.ts` exports `Agent`.

### Performance

- No premature optimisation. Profile before optimising.
- Async correctness > async optimality. A correct sequential
  implementation is better than a buggy parallel one.

### Security

- Never log API keys, tokens, full user prompts at INFO+.
- Use field-level redaction in observability hooks (`redact:
  ["api_key"]` config).
- Subprocess calls use absolute paths; never `shell=True` (Py) /
  `shell: true` (TS) without explicit justification and a feat-018
  capability gate.

## References

- [`AGENTS.md`](../../AGENTS.md) — top-level rules
- [`docs/design/design-principles.md`](../../docs/design/design-principles.md) — P1, P3, P5, P6, P7, P9, P11
- [ruff docs](https://docs.astral.sh/ruff/)
- [mypy docs](https://mypy.readthedocs.io/)
- [biome docs](https://biomejs.dev/)
