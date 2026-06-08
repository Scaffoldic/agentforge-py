"""Same agent code, any provider — the backend is chosen by config, not code.

Point this one file at whichever provider config you like:

    python agent.py "Summarise the Agile Manifesto in three bullets." agentforge.anthropic.yaml
    python agent.py "Summarise the Agile Manifesto in three bullets." agentforge.openai.yaml

The *only* difference between those two runs is one line of YAML
(`agent.model:`). This Python file never changes. That is the whole claim:
swapping the backend is a config edit, and because the swap happens behind a
locked contract it cannot quietly change the shape of what your code gets back.

Requires the matching provider package + API key:

    pip install "agentforge-py[anthropic]"   # or [openai]
    export ANTHROPIC_API_KEY=...             # or OPENAI_API_KEY

No keys handy? Run `smoke.py` instead — it exercises the same loop offline.
"""

from __future__ import annotations

import asyncio
import sys

from agentforge import Agent


async def run(task: str, config_path: str) -> None:
    """Build an agent from `config_path` and run it against `task`."""
    async with Agent(config_path=config_path) as agent:
        result = await agent.run(task)
    print(result.output)
    print(f"\n[run_id={result.run_id} cost=${result.cost_usd:.4f}]")


def main() -> None:
    if len(sys.argv) != 3:  # noqa: PLR2004 — argv[0] + task + config
        print('Usage: python agent.py "<task>" <config.yaml>')
        raise SystemExit(1)
    asyncio.run(run(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
