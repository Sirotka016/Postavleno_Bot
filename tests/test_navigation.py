import asyncio
import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from postavleno_bot.navigation import (
    SCREEN_AUTH_MENU,
    SCREEN_HOME,
    SCREEN_LOGIN,
    ScreenState,
    current_screen,
    nav_back,
    nav_push,
    nav_replace,
    nav_root,
)


def test_navigation_stack_behaviour() -> None:
    async def runner() -> None:
        storage = MemoryStorage()
        ctx = FSMContext(storage=storage, key=StorageKey(bot_id=0, chat_id=1, user_id=1))

        await nav_root(ctx, ScreenState(SCREEN_HOME))
        screen = await current_screen(ctx)
        assert screen and screen.name == SCREEN_HOME

        await nav_push(ctx, ScreenState(SCREEN_AUTH_MENU))
        screen = await current_screen(ctx)
        assert screen and screen.name == SCREEN_AUTH_MENU

        await nav_replace(ctx, ScreenState(SCREEN_LOGIN, {"await_password": False}))
        screen = await current_screen(ctx)
        assert screen and screen.name == SCREEN_LOGIN
        assert screen.params == {"await_password": False}

        await nav_back(ctx)
        screen = await current_screen(ctx)
        assert screen and screen.name == SCREEN_HOME

    asyncio.run(runner())
