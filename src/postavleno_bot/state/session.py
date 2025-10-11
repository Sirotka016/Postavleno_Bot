from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ScreenState:
    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatSession:
    last_bot_message_id: int | None = None
    history: list[ScreenState] = field(default_factory=list)
    # WB
    stocks_wh_map: dict[str, str] = field(default_factory=dict)
    stocks_view: str | None = None  # "ALL" | "wh:abcd1234" | "summary" | None
    stocks_page: int = 1  # current page (>=1)


class SessionStorage:
    """In-memory storage for chat sessions."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[int, ChatSession] = {}

    async def get_last_message_id(self, chat_id: int) -> int | None:
        async with self._lock:
            return self._sessions.get(chat_id, ChatSession()).last_bot_message_id

    async def set_last_message_id(self, chat_id: int, message_id: int) -> None:
        async with self._lock:
            session = self._sessions.setdefault(chat_id, ChatSession())
            session.last_bot_message_id = message_id

    async def clear(self, chat_id: int) -> None:
        async with self._lock:
            self._sessions.pop(chat_id, None)

    async def get_session(self, chat_id: int) -> ChatSession:
        async with self._lock:
            return self._sessions.setdefault(chat_id, ChatSession())

    async def update_session(self, chat_id: int, **fields: object) -> ChatSession:
        async with self._lock:
            session = self._sessions.setdefault(chat_id, ChatSession())
            for name, value in fields.items():
                if hasattr(session, name):
                    setattr(session, name, value)
            return session


session_storage = SessionStorage()


def nav_push(session: ChatSession, screen: ScreenState) -> None:
    session.history.append(screen)


def nav_replace(session: ChatSession, screen: ScreenState) -> None:
    if session.history:
        session.history[-1] = screen
    else:
        session.history.append(screen)


def nav_back(session: ChatSession) -> ScreenState | None:
    if not session.history:
        return None

    if len(session.history) == 1:
        return session.history[0]

    session.history.pop()
    return session.history[-1]
