"""Handlers for the home screen and global actions."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..navigation import (
    SCREEN_AUTH_MENU,
    SCREEN_PROFILE,
    current_screen,
)
from ..services.accounts import AccountNotFoundError, get_accounts_repo
from .pages import render_auth_menu, render_home, render_profile
from .utils import get_auth_user, set_auth_user

router = Router()


async def _show_current(message: Message | CallbackQuery, state: FSMContext) -> None:
    bot = message.bot
    chat_id = message.chat.id if isinstance(message, Message) else message.message.chat.id  # type: ignore[union-attr]
    screen = await current_screen(state)
    repo = get_accounts_repo()
    auth_user = await get_auth_user(state)
    if screen and screen.name == SCREEN_PROFILE and auth_user:
        try:
            profile = repo.get(auth_user)
        except AccountNotFoundError:
            await set_auth_user(state, None)
            await render_home(bot, state, chat_id, nav_action="root")
        else:
            await render_profile(bot, state, chat_id, profile, nav_action="replace")
    elif screen and screen.name == SCREEN_AUTH_MENU:
        await render_auth_menu(bot, state, chat_id, nav_action="replace")
    else:
        await render_home(bot, state, chat_id, nav_action="root")


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    await state.set_state(None)
    repo = get_accounts_repo()
    auth_user = await get_auth_user(state)
    if auth_user:
        try:
            profile = repo.get(auth_user)
        except AccountNotFoundError:
            await set_auth_user(state, None)
            await render_home(message.bot, state, message.chat.id, nav_action="root")
        else:
            await render_profile(message.bot, state, message.chat.id, profile, nav_action="root")
    else:
        await render_home(message.bot, state, message.chat.id, nav_action="root")


@router.callback_query(F.data == "home.auth")
async def open_auth_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(None)
    await render_auth_menu(callback.bot, state, callback.message.chat.id, nav_action="push")


@router.callback_query(F.data == "home.refresh")
async def refresh_home(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(None)
    await _show_current(callback, state)


@router.callback_query(F.data == "home.exit")
async def exit_to_home(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.clear()
    await render_home(callback.bot, state, callback.message.chat.id, nav_action="root")
