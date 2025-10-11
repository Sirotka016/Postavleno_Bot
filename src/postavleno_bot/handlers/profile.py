"""Handlers for the profile screen and editors."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..domain import validate_ms, validate_wb
from ..services.accounts import AccountNotFoundError, get_accounts_repo
from ..state import EditMSState, EditWBState
from .pages import (
    SUCCESS_SAVED,
    render_auth_menu,
    render_edit_email,
    render_edit_ms,
    render_edit_wb,
    render_profile,
)
from .utils import delete_user_message, get_auth_user, set_auth_user

router = Router()


async def _load_profile(state: FSMContext):
    repo = get_accounts_repo()
    username = await get_auth_user(state)
    if not username:
        return None
    try:
        return repo.get(username)
    except AccountNotFoundError:
        await set_auth_user(state, None)
        return None


@router.callback_query(F.data == "profile.refresh")
async def refresh_profile(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await _load_profile(state)
    if not profile:
        await render_auth_menu(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await render_profile(callback.bot, state, callback.message.chat.id, profile, nav_action="replace")


@router.callback_query(F.data == "profile.logout")
async def logout_profile(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await set_auth_user(state, None)
    await state.set_state(None)
    await render_auth_menu(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "profile.wb")
async def edit_wb(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await _load_profile(state)
    if not profile:
        await render_auth_menu(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(EditWBState.await_token)
    await render_edit_wb(callback.bot, state, callback.message.chat.id, nav_action="push")


@router.callback_query(F.data == "profile.ms")
async def edit_ms(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await _load_profile(state)
    if not profile:
        await render_auth_menu(callback.bot, state, callback.message.chat.id, nav_action="replace")
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
    profile = await _load_profile(state)
    if not profile:
        await render_auth_menu(message.bot, state, message.chat.id, nav_action="replace")
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
    profile = await _load_profile(state)
    if not profile:
        await render_auth_menu(message.bot, state, message.chat.id, nav_action="replace")
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
