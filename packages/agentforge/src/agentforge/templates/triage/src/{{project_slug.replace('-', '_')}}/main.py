"""Entry point for {{ project_name }}.

Triage: classify incoming items into severity + category. No
external tools by default — the agent works from the text alone.
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

from agentforge import Agent

load_dotenv()


async def run_agent(item: str) -> str:
    async with Agent() as agent:
        result = await agent.run(item)
        return str(result.output)


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: {{ project_slug }} "<item to triage>"')
        sys.exit(1)
    output = asyncio.run(run_agent(" ".join(sys.argv[1:])))
    print(output)


if __name__ == "__main__":
    main()
