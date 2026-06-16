"""Seed the offline demo recording used by the README hero gif.

Records ONE agent run against a scripted `FakeLLMClient` — no API key, no
network — into a SQLite memory store, so `agentforge run --replay <id>`
can replay it deterministically forever (the gif's "it really runs,
offline" beat). Run from the example directory:

    python seed_recording.py

It (re)writes `demo-recording.sqlite` and prints the `run_id` to wire
into `agentforge.demo.yaml` / `demo.tape`.

Why a recording instead of a live call: the CLI resolves a *model
string* against an installed provider, and there is no offline provider
string. `--replay` sidesteps that — it swaps in a `ReplayLLMClient`
backed by this recording, so the full loop (budget accounting, run-id
propagation) runs with no provider, no key, no network. The token
counts / cost below are a representative Sonnet-class turn so the
footer shows realistic numbers rather than $0.0000.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from agentforge import Agent
from agentforge._testing import FakeLLMClient, echo_response
from agentforge_memory_sqlite import SqliteMemoryStore

DB_PATH = Path(__file__).parent / "demo-recording.sqlite"
TASK = "Summarise the Agile Manifesto in three bullets."
ANSWER = (
    "- Individuals and interactions over processes and tools\n"
    "- Working software over comprehensive documentation\n"
    "- Responding to change over following a plan"
)


async def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    store = await SqliteMemoryStore.from_path(DB_PATH)
    fake = FakeLLMClient(
        responses=[
            echo_response(
                content=ANSWER,
                input_tokens=287,
                output_tokens=41,
                cost_usd=0.0031,
            )
        ]
    )
    async with Agent(model=fake, strategy="react", record_runs=store) as agent:
        result = await agent.run(TASK)
    await store.close()

    print(result.output)
    print(f"\n[run_id={result.run_id} cost=${result.cost_usd:.4f} finish={result.finish_reason}]")
    print(f"\nRecorded to {DB_PATH.name}. Replay it offline with:")
    print(f"  agentforge run --replay {result.run_id} --path agentforge.demo.yaml '{TASK}'")


if __name__ == "__main__":
    asyncio.run(main())
