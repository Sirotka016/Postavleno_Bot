"""Handlers for the home screen and global actions."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..core.logging import get_logger
from ..navigation import SCREEN_AUTH_MENU, SCREEN_PROFILE, current_screen
from ..services.accounts import delete_account
from ..services.sessions import session_store
from ..ui import card_manager
from .pages import (
    render_delete_confirm,
    render_delete_error,
    render_home,
    render_profile,
    render_require_auth,
)
from .utils import load_active_profile, set_auth_user

router = Router()

app_logger = get_logger(__name__).bind(handler="home")
audit_logger = get_logger("audit").bind(action="account_delete")


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


@router.callback_query(F.data == "home.profile")
async def open_profile(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(None)
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await render_profile(callback.bot, state, callback.message.chat.id, profile, nav_action="push")


@router.callback_query(F.data == "home.logout")
async def logout_profile(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await set_auth_user(state, None)
    await state.set_state(None)
    await _render_home(callback, state, callback.message.chat.id, nav_action="root")


@router.callback_query(F.data == "home.delete_open")
async def handle_delete_open(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_delete_confirm(callback.bot, state, callback.message.chat.id, nav_action="push")


@router.callback_query(F.data == "home.delete_cancel")
async def handle_delete_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await set_auth_user(state, None)
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_home(
        callback.bot,
        state,
        callback.message.chat.id,
        nav_action="replace",
        is_authed=True,
        profile=profile,
    )


@router.callback_query(F.data == "home.delete_confirm")
async def handle_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    chat_id = callback.message.chat.id
    profile = await load_active_profile(state)
    if not profile:
        await callback.answer()
        await set_auth_user(state, None)
        await render_require_auth(callback.bot, state, chat_id, nav_action="replace")
        return

    username = profile.username
    audit_log = audit_logger.bind(chat_id=chat_id, username=username)
    logger = app_logger.bind(action="account.delete", chat_id=chat_id, username=username)

    await state.set_state(None)
    await set_auth_user(state, None)
    session_store.remove(chat_id)

    try:
        delete_account(username)
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.exception("Failed to delete account", exception=str(exc))
        audit_log.error("account delete failed", result="failed", reason=str(exc))
        await callback.answer()
        await render_delete_error(callback.bot, state, chat_id, nav_action="replace")
        return

    logger.info("Account deleted successfully")
    audit_log.info("account delete succeeded", result="success", reason=None)
    await callback.answer("Аккаунт удалён. Вы можете создать новый в любое время.")
    await state.set_state(None)
    await render_home(
        callback.bot,
        state,
        chat_id,
        nav_action="root",
        is_authed=False,
        profile=None,
    )


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
    await state.set_state(None)
    await card_manager.close(callback.bot, callback.message.chat.id, state=state)
