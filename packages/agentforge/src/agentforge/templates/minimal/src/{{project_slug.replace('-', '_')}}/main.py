"""Entry point for {{ project_name }}.

Edit this file to add tools, prompts, evaluators, etc. The
`Agent` constructor surface is feat-001's locked Public API — see
`docs/features/feat-001-core-contracts-and-agent.md` in the
agentforge-py repo for every kwarg.
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

from agentforge import Agent

load_dotenv()


async def run_agent(task: str) -> str:
    """Run the agent against `task` and return its output."""
    async with Agent() as agent:
        result = await agent.run(task)
        return str(result.output)


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: {{ project_slug }} "<task>"')
        sys.exit(1)
    task = " ".join(sys.argv[1:])
    output = asyncio.run(run_agent(task))
    print(output)


if __name__ == "__main__":
    main()
