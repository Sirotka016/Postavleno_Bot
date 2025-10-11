"""Utility helpers shared across handlers."""

from __future__ import annotations

from contextlib import suppress

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..core.config import get_settings

AUTH_USER_KEY = "auth_user"


async def get_auth_user(state: FSMContext) -> str | None:
    data = await state.get_data()
    value = data.get(AUTH_USER_KEY)
    return str(value) if isinstance(value, str) else None


async def set_auth_user(state: FSMContext, username: str | None) -> None:
    await state.update_data(**{AUTH_USER_KEY: username})


async def delete_user_message(message: Message) -> None:
    if not get_settings().delete_user_messages:
        return
    with suppress(Exception):
        await message.delete()
