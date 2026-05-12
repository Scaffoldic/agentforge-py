"""`agentforge-chat` — Chat-agent runtime for AgentForge (feat-020).

Public surface: `ChatSession` (chunk 3) + history drivers
(`InMemoryChatHistory`, `SqliteChatHistory`) + four truncation
strategies (`SlidingWindow`, `TokenBudget`, `SummariseOldest`,
`Hybrid`).
"""

from __future__ import annotations

from agentforge_chat.build import build_chat_session_from_config
from agentforge_chat.history import InMemoryChatHistory
from agentforge_chat.session import ChatSession
from agentforge_chat.sqlite import SqliteChatHistory
from agentforge_chat.tokenisers import (
    Tokeniser,
    anthropic_tokeniser,
    tiktoken_tokeniser,
)
from agentforge_chat.truncation import (
    Hybrid,
    SlidingWindow,
    SummariseOldest,
    TokenBudget,
)

__all__ = [
    "ChatSession",
    "Hybrid",
    "InMemoryChatHistory",
    "SlidingWindow",
    "SqliteChatHistory",
    "SummariseOldest",
    "TokenBudget",
    "Tokeniser",
    "anthropic_tokeniser",
    "build_chat_session_from_config",
    "tiktoken_tokeniser",
]
