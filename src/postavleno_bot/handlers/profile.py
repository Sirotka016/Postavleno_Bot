"""Callbacks for rendering and managing the profile screen."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from ..core.logging import get_logger
from ..services.accounts import delete_account
from ..services.sessions import session_store
from .pages import (
    render_delete_confirm,
    render_delete_error,
    render_home,
    render_profile,
    render_require_auth,
)
from .utils import load_active_profile, set_auth_user

router = Router()

logger = get_logger(__name__).bind(handler="profile")
audit_logger = get_logger("audit").bind(action="account_delete")


@router.callback_query(F.data == "profile.open")
async def open_profile(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="push")
        return

    await state.set_state(None)
    await render_profile(callback.bot, state, callback.message.chat.id, profile, nav_action="push")


@router.callback_query(F.data == "profile.refresh")
async def refresh_profile(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return

    await state.set_state(None)
    await render_profile(callback.bot, state, callback.message.chat.id, profile, nav_action="replace")


@router.callback_query(F.data == "profile.logout")
async def logout_profile(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer("Вы вышли из профиля.")
    await set_auth_user(state, None)
    await state.set_state(None)
    await render_home(
        callback.bot,
        state,
        callback.message.chat.id,
        nav_action="root",
        is_authed=False,
        profile=None,
        tg_user=callback.from_user,
    )


@router.callback_query(F.data == "profile.delete_confirm")
async def open_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return

    await state.set_state(None)
    await render_delete_confirm(callback.bot, state, callback.message.chat.id, nav_action="push")


@router.callback_query(F.data == "profile.delete_no")
async def cancel_delete(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return

    await state.set_state(None)
    await render_profile(callback.bot, state, callback.message.chat.id, profile, nav_action="replace")


@router.callback_query(F.data == "profile.delete_yes")
async def confirm_delete(callback: CallbackQuery, state: FSMContext) -> None:
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
    log = logger.bind(action="delete", chat_id=chat_id, username=username)
    audit = audit_logger.bind(chat_id=chat_id, username=username)

    await callback.answer("Удаляю аккаунт…")
    await state.set_state(None)
    await set_auth_user(state, None)
    session_store.remove(chat_id)

    try:
        delete_account(username)
    except Exception as exc:  # pragma: no cover - defensive branch
        log.exception("failed to delete account", error=str(exc))
        audit.error("account delete failed", result="failed", reason=str(exc))
        await render_delete_error(callback.bot, state, chat_id, nav_action="replace")
        return

    log.info("account deleted")
    audit.info("account delete succeeded", result="success", reason=None)

    await render_home(
        callback.bot,
        state,
        chat_id,
        nav_action="root",
        is_authed=False,
        profile=None,
        tg_user=callback.from_user,
    )


__all__ = ["router"]
