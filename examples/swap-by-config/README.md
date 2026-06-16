# Example: swap the backend by config, not code

This is the runnable proof of AgentForge's headline claim:

> **Every backend is its own package, swapped by editing one line of YAML —
> not by touching your agent code.**

Files:

| File | What it shows |
|------|---------------|
| [`agent.py`](./agent.py) | The agent. **Provider-agnostic** — it never names a vendor. |
| [`agentforge.anthropic.yaml`](./agentforge.anthropic.yaml) | Selects Anthropic. |
| [`agentforge.openai.yaml`](./agentforge.openai.yaml) | Selects OpenAI. |
| [`smoke.py`](./smoke.py) | Runs the loop **offline, no API key**, to prove the install works. |
| [`seed_recording.py`](./seed_recording.py) | Records one offline run into `demo-recording.sqlite` for `--replay`. |
| [`agentforge.demo.yaml`](./agentforge.demo.yaml) | Config that points `modules.memory` at the recording (for the gif). |
| [`demo.tape`](./demo.tape) | The [VHS](https://github.com/charmbracelet/vhs) script that renders `demo.gif`. |

## The whole point, in one diff

The two config files are byte-for-byte identical except for a single line:

```diff
- model: "anthropic:claude-sonnet-4-5"
+ model: "openai:gpt-4o"
```

`agent.py` does **not** change. No imports swapped, no client constructed, no
`if provider == ...` branch. The model string is resolved at runtime against
the installed provider package, behind a locked `LLMClient` contract — so the
swap can't quietly change the shape of what `agent.run(...)` returns.

## Run it offline first (10 seconds, zero setup)

```bash
pip install agentforge-py
python smoke.py
```

You should see a line of output and a `[run_id=… cost=$… finish=…]` footer.
That is the full reasoning loop, budget accounting, and run-id propagation
running against a scripted fake model — no provider, no key, no network.

## Replay the same loop through the CLI (offline, no key)

The README hero gif's "it really runs" beat uses `agentforge run --replay`
against a recorded run, so the full CLI path — config loading, memory wiring,
budget accounting, rich run summary — executes with no provider and no key:

```bash
python seed_recording.py     # writes demo-recording.sqlite, prints a run_id
agentforge run --replay <run_id> --path agentforge.demo.yaml \
  "Summarise the Agile Manifesto in three bullets."
```

`agentforge.demo.yaml` configures `modules.memory: sqlite` pointing at the
recording; `--replay` substitutes a `ReplayLLMClient` for the live model, so
no provider string is resolved. The recorded token counts / cost are a
representative Sonnet-class turn (the run itself is scripted, not billed).

> Re-running `seed_recording.py` mints a new `run_id` — update the value in
> `demo.tape` if you regenerate the fixture before rendering the gif.

## Then run it for real (pick a provider)

```bash
# Anthropic
pip install "agentforge-py[anthropic]"
export ANTHROPIC_API_KEY=sk-ant-...
python agent.py "Summarise the Agile Manifesto in three bullets." agentforge.anthropic.yaml

# OpenAI — same command, different config, SAME agent.py
pip install "agentforge-py[openai]"
export OPENAI_API_KEY=sk-...
python agent.py "Summarise the Agile Manifesto in three bullets." agentforge.openai.yaml
```

## Why this matters

The swap happens **behind a version-locked `LLMClient` contract**, and each
provider is a **separate package** you install independently. So changing
providers can't silently change the shape of what `agent.run(...)` returns —
the contract holds across the swap. That combination is the point, not the
string change on its own.
