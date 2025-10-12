"""Handlers for the home screen and global actions."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from ..core.logging import get_logger
from ..navigation import SCREEN_AUTH_MENU, SCREEN_PROFILE, current_screen
from ..ui import card_manager
from .pages import render_home, render_profile, render_require_auth
from .utils import load_active_profile

router = Router()


def _source_user(source: Message | CallbackQuery) -> User | None:
    if isinstance(source, Message):
        return source.from_user
    return source.from_user


async def _render_home(
    source: Message | CallbackQuery, state: FSMContext, chat_id: int, *, nav_action: str = "root"
) -> None:
    profile = await load_active_profile(state)
    bot_instance = source.bot
    await render_home(
        bot_instance,
        state,
        chat_id,
        nav_action=nav_action,
        is_authed=profile is not None,
        profile=profile,
        tg_user=_source_user(source),
    )


async def _show_current(message: Message | CallbackQuery, state: FSMContext) -> None:
    bot = message.bot
    chat_id = message.chat.id if isinstance(message, Message) else message.message.chat.id  # type: ignore[union-attr]
    screen = await current_screen(state)
    if screen and screen.name == SCREEN_PROFILE:
        profile = await load_active_profile(state)
        if not profile:
            await render_require_auth(bot, state, chat_id, nav_action="replace")
            return
        await render_profile(bot, state, chat_id, profile, nav_action="replace")
        return
    if screen and screen.name == SCREEN_AUTH_MENU:
        await render_require_auth(bot, state, chat_id, nav_action="replace")
        return
    await _render_home(message, state, chat_id, nav_action="root")


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    await state.set_state(None)
    await _render_home(message, state, message.chat.id, nav_action="root")


@router.callback_query(F.data == "home.refresh")
async def refresh_home(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(None)
    await state.update_data(skip_export_cache=True)
    await _show_current(callback, state)
