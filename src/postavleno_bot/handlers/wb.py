"""Handlers for managing Wildberries API token."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..domain import validate_wb
from ..services.accounts import get_accounts_repo
from ..state import WbStates
from .pages import (
    render_edit_wb,
    render_profile,
    render_require_auth,
    render_wb_delete_confirm,
    render_wb_menu,
)
from .utils import delete_user_message, load_active_profile

router = Router()


async def _ensure_profile(callback: CallbackQuery, state: FSMContext):
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
    return profile


@router.callback_query(F.data == "wb.open")
async def open_wb(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(None)
    token = (profile.wb_api or "").strip()
    if not token:
        await state.set_state(WbStates.waiting_token)
        await render_edit_wb(callback.bot, state, callback.message.chat.id, nav_action="push")
        return

    await render_wb_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="push",
    )


@router.callback_query(F.data == "wb.change")
async def change_wb(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(WbStates.waiting_token)
    await render_edit_wb(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "wb.delete_confirm")
async def delete_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(None)
    await render_wb_delete_confirm(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "wb.delete_no")
async def cancel_delete(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(None)
    await render_wb_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="replace",
    )


@router.callback_query(F.data == "wb.delete_yes")
async def confirm_delete(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    repo = get_accounts_repo()
    updated = repo.set_wb_api(profile.username, None)

    await state.set_state(None)
    await render_profile(
        callback.bot,
        state,
        callback.message.chat.id,
        updated,
        nav_action="replace",
        extra="Ключ WB удалён ✅",
    )


@router.message(WbStates.waiting_token)
async def handle_token(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    token = (message.text or "").strip()
    if not validate_wb(token):
        await render_edit_wb(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            prompt="Проверьте ключ WB: длина должна быть 32–512 символов.",
        )
        return

    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(message.bot, state, message.chat.id, nav_action="replace")
        return

    repo = get_accounts_repo()
    updated = repo.set_wb_api(profile.username, token)

    await state.set_state(None)
    await render_profile(
        message.bot,
        state,
        message.chat.id,
        updated,
        nav_action="replace",
        extra="Ключ WB обновлён ✅",
    )


__all__ = ["router"]
