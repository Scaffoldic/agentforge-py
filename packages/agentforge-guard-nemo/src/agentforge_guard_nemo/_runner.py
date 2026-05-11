"""Internal NeMo Guardrails runner protocol (feat-018).

`NemoInput` / `NemoOutput` consume a `NemoRunner` so tests inject a
fake without `nemoguardrails` installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RailResult:
    """One pass through a NeMo rail.

    `allowed=False` means the rail blocked the content; `rationale`
    carries a short explanation when available (the Colang
    program's response message).
    """

    allowed: bool
    rationale: str | None = None


class NemoRunner(Protocol):
    """Slice of `nemoguardrails.LLMRails` we depend on."""

    async def check_input(self, content: str) -> RailResult: ...

    async def check_output(self, content: str) -> RailResult: ...


class _RealNemoRunner:
    """Production runner — lazy-imports `nemoguardrails.LLMRails`."""

    def __init__(self, config_path: str) -> None:
        self._config_path = config_path
        self._rails: object | None = None

    async def check_input(self, content: str) -> RailResult:
        rails = self._get_rails()
        return await _run_rail(rails, content, stage="input")

    async def check_output(self, content: str) -> RailResult:
        rails = self._get_rails()
        return await _run_rail(rails, content, stage="output")

    def _get_rails(self) -> object:
        if self._rails is not None:
            return self._rails
        try:
            from nemoguardrails import LLMRails, RailsConfig  # noqa: PLC0415
        except ImportError as exc:
            from agentforge_core.production.exceptions import ModuleError  # noqa: PLC0415

            msg = (
                "nemoguardrails is not installed. Install via "
                "`pip install nemoguardrails` to use the `nemo` validator."
            )
            raise ModuleError(msg) from exc
        config = RailsConfig.from_path(self._config_path)
        self._rails = LLMRails(config)
        return self._rails


async def _run_rail(rails: object, content: str, *, stage: str) -> RailResult:
    """Invoke the rails on the content; map their response to
    `RailResult`. NeMo signals refusal with a structured response
    whose `role == "assistant"` and content indicating refusal —
    rather than parsing prose, we treat any non-empty response as
    "the rail wants to intervene" (i.e. blocked)."""
    response = await rails.generate_async(  # type: ignore[attr-defined]
        messages=[{"role": "user", "content": content}],
    )
    text = str(response.get("content") or "") if isinstance(response, dict) else str(response)
    allowed = not text.strip()
    return RailResult(
        allowed=allowed,
        rationale=text.strip() or f"nemo {stage} rail passed",
    )


__all__ = ["NemoRunner", "RailResult"]
