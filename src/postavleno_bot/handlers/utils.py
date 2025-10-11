"""Utility helpers shared across handlers."""

from __future__ import annotations

from contextlib import suppress

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..core.config import get_settings
from ..services.accounts import AccountNotFoundError, AccountProfile, get_accounts_repo
from ..services.sessions import session_store

AUTH_USER_KEY = "auth_user"


def _state_chat_id(state: FSMContext) -> int | None:
    try:
        return state.key.chat_id
    except AttributeError:  # pragma: no cover - defensive guard
        return None


async def get_auth_user(state: FSMContext) -> str | None:
    data = await state.get_data()
    value = data.get(AUTH_USER_KEY)
    if isinstance(value, str) and value:
        return value
    chat_id = _state_chat_id(state)
    if chat_id is None:
        return None
    username = session_store.get(chat_id)
    if username:
        await state.update_data(**{AUTH_USER_KEY: username})
    return username


async def set_auth_user(state: FSMContext, username: str | None) -> None:
    await state.update_data(**{AUTH_USER_KEY: username})
    chat_id = _state_chat_id(state)
    if chat_id is None:
        return
    if username:
        session_store.set(chat_id, username)
    else:
        session_store.remove(chat_id)


async def load_active_profile(state: FSMContext) -> AccountProfile | None:
    username = await get_auth_user(state)
    if not username:
        return None
    repo = get_accounts_repo()
    try:
        return repo.get(username)
    except AccountNotFoundError:
        await set_auth_user(state, None)
        return None


async def delete_user_message(message: Message) -> None:
    if not get_settings().delete_user_messages:
        return
    with suppress(Exception):
        await message.delete()
