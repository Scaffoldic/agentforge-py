"""Offline smoke run — drives the full agent loop with a scripted fake model.

No API keys. No provider packages. No network. Use it to confirm the install
works end to end in about ten seconds:

    python smoke.py

This is deliberately NOT how you build a real agent (see agent.py for that).
It swaps a scripted `FakeLLMClient` in via the same `model=` parameter a real
client would use, so the reasoning loop runs deterministically offline. The
point it proves: the runtime, budget accounting, and run-id propagation are
wired and working before you add a single real provider.
"""

from __future__ import annotations

import asyncio

from agentforge import Agent
from agentforge._testing import FakeLLMClient, echo_response


async def main() -> None:
    """Run one agent turn against a scripted response and print the result."""
    fake = FakeLLMClient(responses=[echo_response(content="Hello from an offline agent run.")])
    async with Agent(model=fake, strategy="react") as agent:
        result = await agent.run("Say hello.")
    print(result.output)
    print(f"[run_id={result.run_id} cost=${result.cost_usd:.4f} finish={result.finish_reason}]")


if __name__ == "__main__":
    asyncio.run(main())
