"""Local test helpers.

Private package (underscore prefix) — these helpers exist only to
support feat-002's tests (and other early features) until feat-016
ships the full public testing API at `agentforge.testing`.

Helpers here:

- `FakeLLMClient` — minimal scripted-response `LLMClient`. Replaced
  by feat-016's `MockLLMClient` (richer: recording / replay /
  capability simulation).
"""

from __future__ import annotations

from agentforge._testing.fake_llm import FakeLLMClient, echo_response

__all__ = ["FakeLLMClient", "echo_response"]
