"""Handlers for the profile screen and editors."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..domain import validate_company_name, validate_wb
from ..services.accounts import get_accounts_repo
from ..state import EditCompanyState, EditEmailState, EditWBState
from .pages import (
    render_edit_company,
    render_edit_email,
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


@router.callback_query(F.data == "profile.company")
async def edit_company(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(EditCompanyState.await_name)
    await render_edit_company(callback.bot, state, callback.message.chat.id, nav_action="push")


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


@router.callback_query(F.data == "profile.email")
async def edit_email(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(EditEmailState.await_email)
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
            prompt="Проверьте ключ WB: длина должна быть 32–512 символов.",
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
        extra="Ключ WB обновлён ✅",
    )


@router.message(EditCompanyState.await_name)
async def handle_company_name(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    company_name = message.text or ""
    if not validate_company_name(company_name):
        await render_edit_company(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            prompt="Название должно быть длиной от 1 до 60 символов.",
        )
        return

    repo = get_accounts_repo()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(message.bot, state, message.chat.id, nav_action="replace")
        return

    updated = repo.set_company_name(profile.username, company_name.strip())
    await state.set_state(None)
    await render_profile(
        message.bot,
        state,
        message.chat.id,
        updated,
        nav_action="replace",
        extra="Название компании обновлено ✅",
    )
