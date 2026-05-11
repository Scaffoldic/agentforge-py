"""Built-in basic guardrail validators (feat-018).

Four validators ship in the runtime package as the default tier:

- `PromptInjectionBasic` (`prompt_injection_basic`) — regex-based
  pattern matching for the common prompt-injection phrases.
- `PIIRedactBasic` (`pii_redact_basic`) — regex-based PII
  detection + redaction (email / phone / SSN / credit-card /
  IPv4). Output validator; sets `redacted_content`.
- `CapabilityCheck` (`capability_check`) — denies tools that
  declare a `destructive` capability unless explicitly
  allowlisted.
- `Allowlist` (`allowlist`) — bare-name allowlist for tool gates.

All four register themselves with the global Resolver under the
matching category (`guardrails.input` / `guardrails.output` /
`guardrails.tool_gates`) at import time.
"""

from __future__ import annotations

from agentforge.guardrails.allowlist import Allowlist
from agentforge.guardrails.capability_check import CapabilityCheck
from agentforge.guardrails.pii_redact_basic import PIIRedactBasic
from agentforge.guardrails.prompt_injection_basic import PromptInjectionBasic

__all__ = [
    "Allowlist",
    "CapabilityCheck",
    "PIIRedactBasic",
    "PromptInjectionBasic",
]
