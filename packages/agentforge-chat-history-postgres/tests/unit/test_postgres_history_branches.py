"""Additional unit tests covering `PostgresChatHistory` branches not
exercised by the ABC conformance suite (load filters, list_sessions
without owner, metadata coercion, tool-call round-trip)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from agentforge_chat_history_postgres import PostgresChatHistory
from agentforge_chat_history_postgres._inmem_runner import PostgresFakeRunner
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.chat import ChatTurn
from agentforge_core.values.messages import ToolCall


def _turn(turn_id: str, session_id: str, ts: datetime, role: str = "user") -> ChatTurn:
    return ChatTurn(
        id=turn_id,
        session_id=session_id,
        role=role,
        content=f"msg-{turn_id}",
        timestamp=ts,
    )


@pytest.mark.asyncio
async def test_load_filters_before_after_and_roles() -> None:
    runner = PostgresFakeRunner()
    store = await PostgresChatHistory.from_dsn("p", runner=runner)
    now = datetime.now(UTC)
    await store.append(_turn("a", "s", now - timedelta(minutes=2), role="user"))
    await store.append(_turn("b", "s", now - timedelta(minutes=1), role="assistant"))
    await store.append(_turn("c", "s", now, role="user"))

    before = await store.load("s", before=now - timedelta(seconds=30))
    assert {t.id for t in before} == {"a", "b"}
    after = await store.load("s", after=now - timedelta(seconds=30))
    assert {t.id for t in after} == {"c"}
    roles_only = await store.load("s", roles=["assistant"])
    assert {t.id for t in roles_only} == {"b"}


@pytest.mark.asyncio
async def test_list_sessions_without_owner_returns_all() -> None:
    runner = PostgresFakeRunner()
    store = await PostgresChatHistory.from_dsn("p", runner=runner)
    now = datetime.now(UTC)
    await store.append(_turn("t", "s", now))
    sessions = await store.list_sessions()
    assert {s.id for s in sessions} == {"s"}


@pytest.mark.asyncio
async def test_list_sessions_with_before_filter() -> None:
    runner = PostgresFakeRunner()
    store = await PostgresChatHistory.from_dsn("p", runner=runner)
    now = datetime.now(UTC)
    await store.append(_turn("a", "old", now - timedelta(hours=1)))
    await store.append(_turn("b", "new", now))
    sessions = await store.list_sessions(before=now - timedelta(minutes=30))
    assert {s.id for s in sessions} == {"old"}


@pytest.mark.asyncio
async def test_update_metadata_unknown_session_raises() -> None:
    runner = PostgresFakeRunner()
    store = await PostgresChatHistory.from_dsn("p", runner=runner)
    with pytest.raises(ModuleError, match="unknown session"):
        await store.update_session_metadata("nope", {"k": "v"})


@pytest.mark.asyncio
async def test_turn_with_tool_call_round_trips() -> None:
    runner = PostgresFakeRunner()
    store = await PostgresChatHistory.from_dsn("p", runner=runner)
    now = datetime.now(UTC)
    tc = ToolCall(id="call_1", name="search", arguments={"q": "x"})
    turn = ChatTurn(
        id="t1",
        session_id="s",
        role="assistant",
        content="ran",
        timestamp=now,
        tool_calls=(tc,),
    )
    await store.append(turn)
    loaded = await store.load("s")
    assert loaded[0].tool_calls[0].name == "search"
