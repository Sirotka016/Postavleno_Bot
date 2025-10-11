"""Handlers for the profile screen and editors."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..domain import validate_ms, validate_wb
from ..services.accounts import get_accounts_repo
from ..state import EditMSState, EditWBState
from .pages import (
    SUCCESS_SAVED,
    render_edit_email,
    render_edit_ms,
    render_edit_wb,
    render_profile,
    render_require_auth,
)
from .utils import delete_user_message, load_active_profile

router = Router()


@router.callback_query(F.data == "profile.refresh")
async def refresh_profile(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await render_profile(callback.bot, state, callback.message.chat.id, profile, nav_action="replace")


@router.callback_query(F.data == "profile.wb")
async def edit_wb(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(EditWBState.await_token)
    await render_edit_wb(callback.bot, state, callback.message.chat.id, nav_action="push")


@router.callback_query(F.data == "profile.ms")
async def edit_ms(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(EditMSState.await_token)
    await render_edit_ms(callback.bot, state, callback.message.chat.id, nav_action="push")


@router.callback_query(F.data == "profile.email")
async def edit_email(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await render_edit_email(callback.bot, state, callback.message.chat.id, nav_action="push")


@router.message(EditWBState.await_token)
async def handle_wb_token(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    token = (message.text or "").strip()
    if not validate_wb(token):
        await render_edit_wb(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            prompt="Ключ WB должен содержать 32–4096 символов латиницы/цифр и . _ - =",
        )
        return
    repo = get_accounts_repo()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(message.bot, state, message.chat.id, nav_action="replace")
        return
    updated = repo.set_wb_api(profile.username, token)
    await state.set_state(None)
    await render_profile(
        message.bot,
        state,
        message.chat.id,
        updated,
        nav_action="replace",
        extra=SUCCESS_SAVED,
    )


@router.message(EditMSState.await_token)
async def handle_ms_token(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    token = (message.text or "").strip()
    if not validate_ms(token):
        await render_edit_ms(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            prompt="Ключ «Мой Склад» должен содержать 16–4096 символов латиницы/цифр и . _ : / + = -",
        )
        return
    repo = get_accounts_repo()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(message.bot, state, message.chat.id, nav_action="replace")
        return
    updated = repo.set_ms_api(profile.username, token)
    await state.set_state(None)
    await render_profile(
        message.bot,
        state,
        message.chat.id,
        updated,
        nav_action="replace",
        extra=SUCCESS_SAVED,
    )
