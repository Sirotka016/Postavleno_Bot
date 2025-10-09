from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
import structlog


class UserContextMiddleware(BaseMiddleware):
    """Bind chat and user information to the logging context."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        chat_id = None
        user_id = None
        update_type = event.__class__.__name__.lower()

        if isinstance(event, Message):
            chat_id = event.chat.id
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id if event.message else None
            user_id = event.from_user.id

        data["chat_id"] = chat_id
        data["user_id"] = user_id
        data["update_type"] = update_type
        structlog.contextvars.bind_contextvars(
            chat_id=chat_id,
            user_id=user_id,
            update_type=update_type,
        )
        try:
            return await handler(event, data)
        finally:
            try:
                structlog.contextvars.unbind_contextvars("chat_id", "user_id", "update_type")
            except LookupError:
                structlog.contextvars.clear_contextvars()
