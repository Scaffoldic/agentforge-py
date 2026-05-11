"""LLM recording + replay (feat-016 chunk 3).

`record_llm(real_client, path)` returns a wrapper that proxies
every `.call(...)` to the real provider and appends one JSON line
to `path` recording `{request_hash, request, response}`. Tests
replay via `MockLLMClient.from_recording(path)` which matches by
request hash so reordered calls still work.

JSONL format (versioned):

    {"format_version": 1, "redactions": ["api_key", "authorization"]}
    {"request_hash": "...", "request": {...}, "response": {...}}
    {"request_hash": "...", "request": {...}, "response": {...}}

Header always at line 0. Recordings made under format_version 1
remain loadable when the version bumps.

Redaction applies to system / messages / metadata fields whose
key (case-insensitive) matches one of the redactions list. Values
are replaced with `"<redacted>"` before write. By default,
`api_key` and `authorization` are redacted; pass `redactions=[...]`
to extend or replace.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agentforge_core.contracts.llm import LLMClient
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.messages import LLMResponse, Message, ToolSpec

_FORMAT_VERSION = 1
_DEFAULT_REDACTIONS: tuple[str, ...] = ("api_key", "authorization", "bearer")


class _RecordingLLMClient(LLMClient):
    """Wraps a real `LLMClient`; records each call to a JSONL path."""

    def __init__(
        self,
        *,
        real: LLMClient,
        path: Path,
        redactions: tuple[str, ...],
    ) -> None:
        self._real = real
        self._path = path
        self._redactions = redactions
        self._initialised = False

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        response = await self._real.call(system, messages, tools)
        self._ensure_header()
        request = _redact(
            {
                "system": system,
                "messages": [m.model_dump(mode="json") for m in messages],
                "tools": [t.model_dump(mode="json", by_alias=True) for t in (tools or [])],
            },
            self._redactions,
        )
        record = {
            "request_hash": _hash_request(request),
            "request": request,
            "response": response.model_dump(mode="json"),
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return response

    async def close(self) -> None:
        await self._real.close()

    def _ensure_header(self) -> None:
        if self._initialised:
            return
        # Header is written exactly once. Re-recording over an
        # existing file replaces the file outright; appending without
        # a header would corrupt format detection.
        if not self._path.exists() or self._path.stat().st_size == 0:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "format_version": _FORMAT_VERSION,
                            "redactions": list(self._redactions),
                        }
                    )
                    + "\n"
                )
        self._initialised = True


def record_llm(
    real: LLMClient,
    path: str | Path,
    *,
    redactions: tuple[str, ...] | None = None,
) -> LLMClient:
    """Return an `LLMClient` that proxies `real` and records to `path`.

    Replay via `MockLLMClient.from_recording(path)`.

    Redactions default to `("api_key", "authorization", "bearer")`.
    Pass an empty tuple to disable redaction entirely (only for
    truly local recordings).
    """
    return _RecordingLLMClient(
        real=real,
        path=Path(path),
        redactions=redactions if redactions is not None else _DEFAULT_REDACTIONS,
    )


def load_recording(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse a recording file into `(header, entries)`.

    `header` carries `format_version` + `redactions`. `entries` is
    the list of `{request_hash, request, response}` records in
    on-disk order.
    """
    p = Path(path)
    if not p.exists():
        msg = f"recording {p!r} does not exist."
        raise ModuleError(msg)
    lines = [line for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        msg = f"recording {p!r} is empty."
        raise ModuleError(msg)
    header = json.loads(lines[0])
    if header.get("format_version") != _FORMAT_VERSION:
        msg = (
            f"recording {p!r}: format_version={header.get('format_version')!r} "
            f"not supported (this build accepts version {_FORMAT_VERSION})."
        )
        raise ModuleError(msg)
    entries = [json.loads(line) for line in lines[1:]]
    return header, entries


def _hash_request(request: dict[str, Any]) -> str:
    """Stable hash of a redacted request for replay lookup.

    Hashing happens AFTER redaction so the cassette is portable
    across environments with different api_key values.
    """
    blob = json.dumps(request, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _redact(payload: Any, keys: tuple[str, ...]) -> Any:
    """Recursively replace any dict-value whose key matches one of
    `keys` (case-insensitive) with `"<redacted>"`."""
    if isinstance(payload, dict):
        result: dict[str, Any] = {}
        for k, v in payload.items():
            if isinstance(k, str) and k.lower() in keys:
                result[k] = "<redacted>"
            else:
                result[k] = _redact(v, keys)
        return result
    if isinstance(payload, list):
        return [_redact(item, keys) for item in payload]
    return payload


__all__ = ["load_recording", "record_llm"]
