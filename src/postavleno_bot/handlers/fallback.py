"""Fallback handlers for unexpected user input."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..navigation import (
    SCREEN_AUTH_MENU,
    SCREEN_HOME,
    SCREEN_LOGIN,
    SCREEN_PROFILE,
    SCREEN_REGISTER,
    nav_back,
)
from ..services.accounts import AccountNotFoundError, get_accounts_repo
from ..state import LoginStates, RegisterStates
from .pages import (
    render_auth_menu,
    render_home,
    render_login,
    render_profile,
    render_register,
    render_unknown,
)
from .utils import delete_user_message, get_auth_user

router = Router()


@router.message()
async def handle_unknown_message(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    await state.set_state(None)
    await render_unknown(message.bot, state, message.chat.id, nav_action="push")


@router.callback_query(F.data == "unknown.repeat")
async def repeat_previous(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    previous = await nav_back(state)
    if not previous:
        await render_home(callback.bot, state, callback.message.chat.id, nav_action="root")
        return

    repo = get_accounts_repo()
    auth_user = await get_auth_user(state)

    if previous.name == SCREEN_HOME:
        await render_home(callback.bot, state, callback.message.chat.id, nav_action="root")
    elif previous.name == SCREEN_AUTH_MENU:
        await render_auth_menu(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_LOGIN:
        await state.set_state(LoginStates.await_login)
        await render_login(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_REGISTER:
        await state.set_state(RegisterStates.await_login)
        await render_register(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_PROFILE and auth_user:
        try:
            profile = repo.get(auth_user)
        except AccountNotFoundError:
            await render_home(callback.bot, state, callback.message.chat.id, nav_action="root")
        else:
            await render_profile(callback.bot, state, callback.message.chat.id, profile, nav_action="replace")
    else:
        await render_home(callback.bot, state, callback.message.chat.id, nav_action="root")
