# Test fixtures

All test inputs, scripted mock-LLM responses, expected outputs, and
threshold values live here as YAML / JSON files. **No test hardcodes
these values.** See `.claude/standards/configuration.md` (in the design
workspace) for the rule.

## Layout

```
tests/fixtures/
├── README.md                      this file
├── thresholds.yaml                tunable thresholds (timeouts, retry counts)
├── agents/                        complete agentforge.yaml fixtures
├── llm/                           scripted mock-LLM scenarios (JSONL)
├── findings/                      expected findings per scenario
└── ...                            (one subdir per fixture category)
```

## Adding a fixture

1. Pick the right subdirectory (or create one with a clear name).
2. Use YAML for structured data; JSONL for sequential scripts (LLM
   responses).
3. Reference from a fixture in `conftest.py`, not directly in the test
   body — that way the same data can power multiple tests.
4. If the fixture has thresholds (numbers that might tune), put them
   in `thresholds.yaml` instead.
