from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass(slots=True)
class ChatSession:
    last_bot_message_id: int | None = None
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
