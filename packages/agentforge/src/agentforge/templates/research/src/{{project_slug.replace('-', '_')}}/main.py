"""Entry point for {{ project_name }}.

Research with citations. Plan-Execute strategy + web_search.
Outputs NarrativeFinding (feat-008).
"""

from __future__ import annotations

import asyncio
import sys

from agentforge import Agent
from agentforge.tools import web_search


async def run_agent(question: str) -> str:
    async with Agent(tools=[web_search]) as agent:
        result = await agent.run(question)
        return str(result.output)


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m {{ project_slug | replace("-", "_") }} "<research question>"')
        sys.exit(1)
    output = asyncio.run(run_agent(" ".join(sys.argv[1:])))
    print(output)


if __name__ == "__main__":
    main()
