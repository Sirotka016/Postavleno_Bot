"""Handlers for the profile screen and editors."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..domain import validate_company_name, validate_wb
from ..services.accounts import get_accounts_repo
from ..state import EditCompanyState, EditEmailState, EditWBState
from .pages import (
    render_company_delete_confirm,
    render_company_menu,
    render_company_prompt,
    render_edit_email,
    render_edit_wb,
    render_email_menu,
    render_email_unlink_confirm,
    render_profile,
    render_require_auth,
    render_wb_delete_confirm,
    render_wb_menu,
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
    await state.set_state(None)
    company = (profile.company_name or "").strip()
    if not company:
        await state.set_state(EditCompanyState.await_name)
        await state.update_data(company_rename=False)
        await render_company_prompt(
            callback.bot,
            state,
            callback.message.chat.id,
            nav_action="push",
        )
        return
    await render_company_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="push",
    )


@router.callback_query(F.data == "company.refresh")
async def refresh_company(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_company_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="replace",
    )


@router.callback_query(F.data == "company.rename")
async def rename_company(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(EditCompanyState.await_name)
    await state.update_data(company_rename=True)
    await render_company_prompt(
        callback.bot,
        state,
        callback.message.chat.id,
        nav_action="replace",
        rename=True,
    )


@router.callback_query(F.data == "company.delete")
async def delete_company(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_company_delete_confirm(
        callback.bot,
        state,
        callback.message.chat.id,
        nav_action="replace",
    )


@router.callback_query(F.data == "company.delete.cancel")
async def cancel_delete_company(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_company_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="replace",
    )


@router.callback_query(F.data == "company.delete.confirm")
async def confirm_delete_company(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
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
        extra="Готово! Компания обновлена ✅",
    )


@router.callback_query(F.data == "profile.wb")
async def edit_wb(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    token = (profile.wb_api or "").strip()
    if not token:
        await state.set_state(EditWBState.await_token)
        await render_edit_wb(callback.bot, state, callback.message.chat.id, nav_action="push")
        return
    await render_wb_menu(callback.bot, state, callback.message.chat.id, nav_action="push")


@router.callback_query(F.data == "wb.refresh")
async def refresh_wb(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    token = (profile.wb_api or "").strip()
    if not token:
        await state.set_state(EditWBState.await_token)
        await render_edit_wb(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_wb_menu(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "wb.edit")
async def change_wb(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(EditWBState.await_token)
    await render_edit_wb(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "wb.delete")
async def delete_wb_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    token = (profile.wb_api or "").strip()
    if not token:
        await state.set_state(EditWBState.await_token)
        await render_edit_wb(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_wb_delete_confirm(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "wb.delete.cancel")
async def cancel_delete_wb(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    token = (profile.wb_api or "").strip()
    if not token:
        await state.set_state(EditWBState.await_token)
        await render_edit_wb(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_wb_menu(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "wb.delete.confirm")
async def confirm_delete_wb(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
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


@router.callback_query(F.data == "profile.email")
async def edit_email(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    if not profile.email:
        await state.set_state(EditEmailState.await_email)
        await render_edit_email(callback.bot, state, callback.message.chat.id, nav_action="push")
        return
    await render_email_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="push",
    )


@router.callback_query(F.data == "email.refresh")
async def refresh_email(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile or not profile.email:
        await state.set_state(EditEmailState.await_email)
        await render_edit_email(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_email_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="replace",
    )


@router.callback_query(F.data == "email.change")
async def change_email(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(EditEmailState.await_email)
    await render_edit_email(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "email.unlink")
async def unlink_email_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_email_unlink_confirm(
        callback.bot,
        state,
        callback.message.chat.id,
        nav_action="replace",
    )


@router.callback_query(F.data == "email.unlink.cancel")
async def cancel_unlink_email(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    if not profile.email:
        await state.set_state(EditEmailState.await_email)
        await render_edit_email(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    await state.set_state(None)
    await render_email_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="replace",
    )


@router.callback_query(F.data == "email.unlink.confirm")
async def confirm_unlink_email(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return
    repo = get_accounts_repo()
    updated = repo.update_fields(
        profile.username,
        email=None,
        email_verified=False,
        email_pending_hash=None,
        email_pending_expires_at=None,
    )
    await state.set_state(None)
    await render_profile(
        callback.bot,
        state,
        callback.message.chat.id,
        updated,
        nav_action="replace",
        extra="Почта отвязана ✅",
    )


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
        data = await state.get_data()
        rename = bool(data.get("company_rename"))
        await render_company_prompt(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            rename=rename,
            prompt="Название должно быть длиной от 1 до 70 символов без переносов строк.",
        )
        return

    repo = get_accounts_repo()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(message.bot, state, message.chat.id, nav_action="replace")
        return

    updated = repo.set_company_name(profile.username, company_name.strip())
    await state.set_state(None)
    await state.update_data(company_rename=None)
    await render_profile(
        message.bot,
        state,
        message.chat.id,
        updated,
        nav_action="replace",
        extra="Готово! Компания обновлена ✅",
    )
