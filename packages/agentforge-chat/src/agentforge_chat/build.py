"""Config-driven `ChatSession` construction (feat-020).

`build_chat_session_from_config(config, agent)` reads
`modules.chat:` and assembles:

  - the history-store driver (resolver category `chat.history`),
  - the truncation strategy (resolver category `chat.truncation`),
  - per-turn / per-session budget + idempotency knobs.

Drivers that expose `from_config(cfg)` are preferred; otherwise
the class is constructed with `**cfg`. Async-factory drivers
(e.g. `SqliteChatHistory.from_path`) are recognised by the
`from_path` classmethod returning an awaitable.
"""

from __future__ import annotations

from typing import Any

from agentforge.agent import Agent
from agentforge_core.config.schema import AgentForgeConfig
from agentforge_core.contracts.chat import ChatHistoryStore, HistoryTruncationStrategy
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import Resolver

from agentforge_chat.history import InMemoryChatHistory
from agentforge_chat.session import ChatSession
from agentforge_chat.truncation import SlidingWindow


async def build_chat_session_from_config(
    config: AgentForgeConfig,
    agent: Agent,
    *,
    session_id: str | None = None,
    owner: str | None = None,
    system_prompt: str | None = None,
) -> ChatSession:
    """Instantiate a `ChatSession` driven by `modules.chat:`.

    Caller still owns the `Agent`; the chat session merely wraps it.
    `session_id` defaults to a fresh ULID-ish hex when omitted.
    """
    chat_cfg = config.modules.chat
    history: ChatHistoryStore = InMemoryChatHistory()
    truncation: HistoryTruncationStrategy = SlidingWindow(50)
    per_turn = None
    per_session = None
    idem_window = 60.0
    if chat_cfg is not None:
        if chat_cfg.history is not None:
            history = await _build_history(chat_cfg.history.driver, chat_cfg.history.config)
        if chat_cfg.truncation is not None:
            truncation = _build_truncation(chat_cfg.truncation.strategy, chat_cfg.truncation.config)
        per_turn = chat_cfg.session.per_turn_budget_usd
        per_session = chat_cfg.session.per_session_budget_usd
        idem_window = chat_cfg.session.idempotency_window_s
    return ChatSession(
        agent=agent,
        session_id=session_id,
        history_store=history,
        system_prompt=system_prompt,
        truncation=truncation,
        owner=owner,
        per_turn_budget_usd=per_turn,
        per_session_budget_usd=per_session,
        idempotency_window_s=idem_window,
    )


async def _build_history(driver: str, cfg: dict[str, Any]) -> ChatHistoryStore:
    cls = Resolver.global_().resolve("chat.history", driver)
    instance = await _maybe_async(_instantiate(cls, cfg))
    if not isinstance(instance, ChatHistoryStore):
        raise ModuleError(
            f"Resolved chat.history driver {driver!r} ({cls.__name__}) does not "
            f"implement ChatHistoryStore."
        )
    return instance


def _build_truncation(name: str, cfg: dict[str, Any]) -> HistoryTruncationStrategy:
    cls = Resolver.global_().resolve("chat.truncation", name)
    instance = _instantiate(cls, cfg)
    if not isinstance(instance, HistoryTruncationStrategy):
        raise ModuleError(
            f"Resolved chat.truncation {name!r} ({cls.__name__}) does not "
            f"implement HistoryTruncationStrategy."
        )
    return instance


def _instantiate(cls: type, cfg: dict[str, Any]) -> Any:
    from_config = getattr(cls, "from_config", None)
    if callable(from_config):
        return from_config(cfg)
    from_path = getattr(cls, "from_path", None)
    if callable(from_path) and "path" in cfg:
        return from_path(cfg["path"])
    return cls(**cfg)


async def _maybe_async(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


__all__ = ["build_chat_session_from_config"]
