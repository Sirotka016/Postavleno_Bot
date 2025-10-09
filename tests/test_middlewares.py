from __future__ import annotations

import asyncio

from aiogram.types import TelegramObject

from postavleno_bot.middlewares.user_context import UserContextMiddleware


def test_user_context_middleware_no_update_type_in_data() -> None:
    middleware = UserContextMiddleware()

    async def fake_handler(event: object, data: dict[str, object]) -> set[str]:
        return set(data.keys())

    keys = asyncio.run(middleware(fake_handler, TelegramObject(), {}))

    assert "update_type" not in keys
