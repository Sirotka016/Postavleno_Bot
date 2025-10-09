from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ChatSession:
    last_bot_message_id: Optional[int] = None


class SessionStorage:
    """In-memory storage for chat sessions."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[int, ChatSession] = {}

    async def get_last_message_id(self, chat_id: int) -> Optional[int]:
        async with self._lock:
            return self._sessions.get(chat_id, ChatSession()).last_bot_message_id

    async def set_last_message_id(self, chat_id: int, message_id: int) -> None:
        async with self._lock:
            session = self._sessions.setdefault(chat_id, ChatSession())
            session.last_bot_message_id = message_id

    async def clear(self, chat_id: int) -> None:
        async with self._lock:
            self._sessions.pop(chat_id, None)


session_storage = SessionStorage()
