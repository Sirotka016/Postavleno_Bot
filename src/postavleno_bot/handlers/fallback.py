"""Fallback handlers for unexpected user input."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..navigation import (
    SCREEN_AUTH_MENU,
    SCREEN_DELETE_CONFIRM,
    SCREEN_HOME,
    SCREEN_LOGIN,
    SCREEN_PROFILE,
    SCREEN_REGISTER,
    nav_back,
)
from ..state import LoginStates, RegisterStates
from .pages import (
    render_delete_confirm,
    render_delete_error,
    render_home,
    render_login,
    render_profile,
    render_register,
    render_require_auth,
    render_unknown,
)
from .utils import delete_user_message, load_active_profile

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
    profile = await load_active_profile(state)
    if not previous:
        await render_home(
            callback.bot,
            state,
            callback.message.chat.id,
            nav_action="root",
            is_authed=profile is not None,
            profile=profile,
        )
        return

    if previous.name == SCREEN_HOME:
        await render_home(
            callback.bot,
            state,
            callback.message.chat.id,
            nav_action="root",
            is_authed=profile is not None,
            profile=profile,
        )
    elif previous.name == SCREEN_AUTH_MENU:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_LOGIN:
        await state.set_state(LoginStates.await_login)
        await render_login(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_REGISTER:
        await state.set_state(RegisterStates.await_login)
        await render_register(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_PROFILE:
        if not profile:
            await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        else:
            await render_profile(callback.bot, state, callback.message.chat.id, profile, nav_action="replace")
    elif previous.name == SCREEN_DELETE_CONFIRM:
        if previous.params.get("error"):
            await render_delete_error(callback.bot, state, callback.message.chat.id, nav_action="replace")
        elif not profile:
            await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        else:
            await render_delete_confirm(callback.bot, state, callback.message.chat.id, nav_action="replace")
    else:
        await render_home(
            callback.bot,
            state,
            callback.message.chat.id,
            nav_action="root",
            is_authed=profile is not None,
            profile=profile,
        )


@router.callback_query(F.data == "unknown.exit")
async def exit_unknown(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(None)
    profile = await load_active_profile(state)
    await render_home(
        callback.bot,
        state,
        callback.message.chat.id,
        nav_action="root",
        is_authed=profile is not None,
        profile=profile,
    )
