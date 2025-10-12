"""Handlers for managing the company section of the profile."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..domain import validate_company_name
from ..services.accounts import get_accounts_repo
from ..state import CompanyStates
from .pages import (
    render_company_delete_confirm,
    render_company_menu,
    render_company_prompt,
    render_profile,
    render_require_auth,
)
from .utils import delete_user_message, load_active_profile

router = Router()


async def _ensure_profile(callback: CallbackQuery, state: FSMContext):
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
    return profile


@router.callback_query(F.data == "company.open")
async def open_company(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(None)
    company = (profile.company_name or "").strip()
    if not company:
        await state.set_state(CompanyStates.waiting_name)
        await state.update_data(company_mode="create")
        await render_company_prompt(callback.bot, state, callback.message.chat.id, nav_action="push")
        return

    await render_company_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="push",
    )


@router.callback_query(F.data == "company.ask_name")
async def refresh_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    data = await state.get_data()
    rename = data.get("company_mode") == "rename"
    await state.set_state(CompanyStates.waiting_name)
    await render_company_prompt(
        callback.bot,
        state,
        callback.message.chat.id,
        nav_action="replace",
        rename=rename,
    )


@router.callback_query(F.data == "company.rename")
async def rename_company(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(CompanyStates.waiting_name)
    await state.update_data(company_mode="rename")
    await render_company_prompt(
        callback.bot,
        state,
        callback.message.chat.id,
        nav_action="replace",
        rename=True,
    )


@router.callback_query(F.data == "company.delete_confirm")
async def delete_company_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(None)
    await render_company_delete_confirm(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "company.delete_no")
async def cancel_delete(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(None)
    await render_company_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="replace",
    )


@router.callback_query(F.data == "company.delete_yes")
async def confirm_delete(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    repo = get_accounts_repo()
    updated = repo.set_company_name(profile.username, "")

    await state.set_state(None)
    await render_profile(
        callback.bot,
        state,
        callback.message.chat.id,
        updated,
        nav_action="replace",
        extra="Компания удалена ✅",
    )


@router.message(CompanyStates.waiting_name)
async def handle_company_name(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    company_name = (message.text or "").strip()
    if not validate_company_name(company_name):
        data = await state.get_data()
        rename = data.get("company_mode") == "rename"
        await render_company_prompt(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            rename=rename,
            prompt="Название должно быть длиной от 1 до 70 символов без переносов строк.",
        )
        return

    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(message.bot, state, message.chat.id, nav_action="replace")
        return

    repo = get_accounts_repo()
    updated = repo.set_company_name(profile.username, company_name)

    await state.set_state(None)
    await state.update_data(company_mode=None)
    await render_profile(
        message.bot,
        state,
        message.chat.id,
        updated,
        nav_action="replace",
        extra="Готово! Компания обновлена ✅",
    )


__all__ = ["router"]
