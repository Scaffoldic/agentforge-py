"""Entry point for {{ project_name }}.

Emits PatchFinding (feat-008) — structured unified diffs with
rationale + confidence. Tools include `file_read` so the bot can
pull source context before proposing a patch.
"""

from __future__ import annotations

import asyncio
import sys

from agentforge import Agent
from agentforge.tools import file_read


async def run_agent(task: str) -> str:
    async with Agent(tools=[file_read]) as agent:
        result = await agent.run(task)
        return str(result.output)


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m {{ project_slug | replace("-", "_") }} "<task>"')
        sys.exit(1)
    output = asyncio.run(run_agent(" ".join(sys.argv[1:])))
    print(output)


if __name__ == "__main__":
    main()
