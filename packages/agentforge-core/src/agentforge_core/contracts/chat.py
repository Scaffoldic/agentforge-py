"""Chat-agent contracts (feat-020).

`ChatHistoryStore` and `HistoryTruncationStrategy` are the two locked
ABCs the chat layer ships against. Drivers (in-memory + sqlite +
postgres + redis) all implement the same `ChatHistoryStore` shape;
truncation strategies (sliding-window, token-budget, summarise-oldest,
hybrid) all implement the same `HistoryTruncationStrategy` shape.

Per ADR-0007, methods on these ABCs are locked once the feature
ships. Adding a method is a major version bump.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from agentforge_core.values.chat import ChatTurn, SessionInfo


class ChatHistoryStore(ABC):
    """Persistent store for chat turns, isolated by `session_id`.

    All read/write methods take `session_id`; cross-session access
    is impossible without explicitly passing the id. Drivers
    typically index on `(session_id, created_at)` so `load()` is
    sub-linear w.r.t. total store size.
    """

    @abstractmethod
    async def append(self, turn: ChatTurn) -> None:
        """Persist a single chat turn."""

    @abstractmethod
    async def load(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        roles: list[str] | None = None,
    ) -> list[ChatTurn]:
        """Load turns for ``session_id`` in chronological order
        (oldest first). Filters apply pre-limit."""

    @abstractmethod
    async def count(self, session_id: str) -> int:
        """Total turn count for ``session_id``."""

    @abstractmethod
    async def delete_session(self, session_id: str) -> int:
        """Delete every turn for ``session_id``. Returns the number
        of turns removed."""

    @abstractmethod
    async def list_sessions(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[SessionInfo]:
        """List sessions, optionally filtered by owner. Ordered by
        ``last_active_at`` descending."""

    @abstractmethod
    async def update_session_metadata(self, session_id: str, metadata: Mapping[str, Any]) -> None:
        """Merge ``metadata`` into the session's metadata dict.

        Implementations may overwrite top-level keys; nested merging
        is the caller's responsibility.
        """

    @abstractmethod
    async def expire_before(self, cutoff: datetime) -> int:
        """TTL sweep: delete every session whose ``last_active_at <
        cutoff``. Returns the number of sessions removed. Drivers
        without TTL support return 0."""

    @abstractmethod
    async def close(self) -> None:
        """Release driver resources (DB pool, file handles, etc.)."""

    def capabilities(self) -> set[str]:
        """Optional capability bag.

        Subset of: ``"ttl"``, ``"encryption_at_rest"``,
        ``"full_text_search"``, ``"streaming_load"``.
        """
        return set()

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities()


class HistoryTruncationStrategy(ABC):
    """Decides which prior turns to include in the next LLM call.

    Truncation runs every turn, between `load()` and the agent call.
    Returns a possibly-empty subset of ``all_turns`` (ordered).
    Invariants every strategy honours (covered by the conformance
    harness):

    - Order-preserving (output is a subsequence of input).
    - Tool-call / tool-result pairs are never split.
    """

    @abstractmethod
    async def select(
        self,
        all_turns: list[ChatTurn],
        next_user_message: str,
        context: Mapping[str, Any],
    ) -> list[ChatTurn]:
        """Return the subset of ``all_turns`` to feed to the LLM."""
