"""Entry point for {{ project_name }}.

Docs / source Q&A. Wires `file_read` + `web_search` so the agent
can pull both local docs and external context. Outputs
`NarrativeFinding`s (feat-008).
"""

from __future__ import annotations

import asyncio
import sys

from agentforge import Agent
from agentforge.tools import file_read, web_search


async def run_agent(task: str) -> str:
    async with Agent(tools=[file_read, web_search]) as agent:
        result = await agent.run(task)
        return str(result.output)


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m {{ project_slug | replace("-", "_") }} "<question>"')
        sys.exit(1)
    output = asyncio.run(run_agent(" ".join(sys.argv[1:])))
    print(output)


if __name__ == "__main__":
    main()
