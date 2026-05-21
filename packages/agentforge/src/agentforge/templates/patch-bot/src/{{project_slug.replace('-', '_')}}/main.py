"""Entry point for {{ project_name }}.

Emits PatchFinding (feat-008) — structured unified diffs with
rationale + confidence. Tools include `file_read` so the bot can
pull source context before proposing a patch.
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

from agentforge import Agent
from agentforge.tools import file_read

load_dotenv()


async def run_agent(task: str) -> str:
    async with Agent(tools=[file_read]) as agent:
        result = await agent.run(task)
        return str(result.output)


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: {{ project_slug }} "<task>"')
        sys.exit(1)
    output = asyncio.run(run_agent(" ".join(sys.argv[1:])))
    print(output)


if __name__ == "__main__":
    main()
