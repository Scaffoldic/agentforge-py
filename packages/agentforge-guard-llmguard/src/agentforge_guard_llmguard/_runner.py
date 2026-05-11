"""Internal LLM Guard runner protocol (feat-018).

`LLMGuardInput` consumes a `LLMGuardRunner` so tests inject a fake
without requiring `llm-guard` to be installed in the test env.
Production code constructs the real wrapper around `llm_guard`'s
`InputScanners` / `OutputScanners`.
"""

from __future__ import annotations

from typing import Any, Protocol


class LLMGuardRunner(Protocol):
    """Minimal slice of `llm_guard` we depend on.

    `scan(content)` returns `(sanitized, valid, scores)` per the
    upstream contract: `valid` is a `{scanner_name: bool}` dict;
    `scores` is `{scanner_name: float}` in [0, 1] where 1 = clean.
    """

    async def scan(
        self,
        content: str,
    ) -> tuple[str, dict[str, bool], dict[str, float]]: ...


class _RealLLMGuardRunner:
    """Production wrapper around the `llm_guard` input scanners.

    Lazy-imports `llm_guard` so the package can be installed without
    the upstream dependency available at import time — useful for
    tests that swap in `LLMGuardFakeRunner`. When `scan` is first
    called, the lazy import resolves; if `llm_guard` isn't
    installed, raises `ModuleError` with a clear remediation hint.
    """

    def __init__(self, scanners: list[Any]) -> None:
        self._scanners = list(scanners)

    async def scan(
        self,
        content: str,
    ) -> tuple[str, dict[str, bool], dict[str, float]]:
        from agentforge_core.production.exceptions import ModuleError  # noqa: PLC0415

        try:
            from llm_guard.evaluate import scan_prompt  # noqa: PLC0415
            from llm_guard.input_scanners.base import Scanner  # noqa: F401, PLC0415
        except ImportError as exc:
            msg = (
                "llm_guard is not installed. Install it via `pip install "
                "llm-guard` to use `LLMGuardInput`."
            )
            raise ModuleError(msg) from exc

        sanitized, results, scores = scan_prompt(self._scanners, content)
        return sanitized, dict(results), dict(scores)


__all__ = ["LLMGuardRunner"]
