"""Entry point for {{ project_name }}.

Triage: classify incoming items into severity + category. No
external tools by default — the agent works from the text alone.
"""

from __future__ import annotations

import asyncio
import sys

from agentforge import Agent


async def run_agent(item: str) -> str:
    async with Agent() as agent:
        result = await agent.run(item)
        return str(result.output)


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m {{ project_slug | replace("-", "_") }} "<item to triage>"')
        sys.exit(1)
    output = asyncio.run(run_agent(" ".join(sys.argv[1:])))
    print(output)


if __name__ == "__main__":
    main()
