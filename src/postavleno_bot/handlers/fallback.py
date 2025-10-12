"""Fallback handlers for unexpected user input."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..navigation import (
    SCREEN_AUTH_MENU,
    SCREEN_DELETE_CONFIRM,
    SCREEN_EDIT_COMPANY,
    SCREEN_EDIT_EMAIL,
    SCREEN_EDIT_WB,
    SCREEN_EXPORT_DONE,
    SCREEN_EXPORT_STATUS,
    SCREEN_HOME,
    SCREEN_LOGIN,
    SCREEN_PROFILE,
    SCREEN_REGISTER,
    nav_back,
)
from ..state import CompanyStates, EmailStates, LoginStates, RegisterStates, WbStates
from .pages import (
    render_company_delete_confirm,
    render_company_menu,
    render_company_prompt,
    render_delete_confirm,
    render_delete_error,
    render_edit_email,
    render_edit_wb,
    render_email_menu,
    render_email_unlink_confirm,
    render_home,
    render_login,
    render_profile,
    render_register,
    render_require_auth,
    render_unknown,
    render_wb_delete_confirm,
    render_wb_menu,
)
from .utils import delete_user_message, load_active_profile

router = Router()


@router.message()
async def handle_unknown_message(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    await state.set_state(None)
    await render_unknown(message.bot, state, message.chat.id, nav_action="push")


@router.callback_query(F.data == "unknown.repeat")
async def repeat_previous(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    previous = await nav_back(state)
    profile = await load_active_profile(state)
    tg_user = callback.from_user
    if not previous:
        await render_home(
            callback.bot,
            state,
            callback.message.chat.id,
            nav_action="root",
            is_authed=profile is not None,
            profile=profile,
            tg_user=tg_user,
        )
        return

    if previous.name == SCREEN_HOME:
        await render_home(
            callback.bot,
            state,
            callback.message.chat.id,
            nav_action="root",
            is_authed=profile is not None,
            profile=profile,
            tg_user=tg_user,
        )
    elif previous.name == SCREEN_AUTH_MENU:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_LOGIN:
        await state.set_state(LoginStates.await_login)
        await render_login(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_REGISTER:
        await state.set_state(RegisterStates.await_login)
        await render_register(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_PROFILE:
        if not profile:
            await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        else:
            await render_profile(callback.bot, state, callback.message.chat.id, profile, nav_action="replace")
    elif previous.name == SCREEN_DELETE_CONFIRM:
        if previous.params.get("error"):
            await render_delete_error(callback.bot, state, callback.message.chat.id, nav_action="replace")
        elif not profile:
            await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
        else:
            await render_delete_confirm(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_EDIT_COMPANY:
        mode = previous.params.get("mode")
        if mode == "menu":
            if not profile:
                await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
            else:
                await state.set_state(None)
                await render_company_menu(
                    callback.bot,
                    state,
                    callback.message.chat.id,
                    profile=profile,
                    nav_action="replace",
                )
        elif mode == "delete":
            await state.set_state(None)
            await render_company_delete_confirm(callback.bot, state, callback.message.chat.id, nav_action="replace")
        else:
            await state.set_state(CompanyStates.waiting_name)
            await render_company_prompt(
                callback.bot,
                state,
                callback.message.chat.id,
                nav_action="replace",
                rename=bool(previous.params.get("rename")),
            )
    elif previous.name == SCREEN_EDIT_WB:
        mode = previous.params.get("mode")
        if mode == "menu":
            if not profile:
                await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
            else:
                await state.set_state(None)
                await render_wb_menu(
                    callback.bot,
                    state,
                    callback.message.chat.id,
                    profile=profile,
                    nav_action="replace",
                )
        elif mode == "delete":
            await state.set_state(None)
            await render_wb_delete_confirm(callback.bot, state, callback.message.chat.id, nav_action="replace")
        else:
            await state.set_state(WbStates.waiting_token)
            await render_edit_wb(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name == SCREEN_EDIT_EMAIL:
        mode = previous.params.get("mode")
        if mode == "menu":
            if not profile:
                await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
            else:
                await state.set_state(None)
                await render_email_menu(
                    callback.bot,
                    state,
                    callback.message.chat.id,
                    profile=profile,
                    nav_action="replace",
                )
        elif mode == "unlink":
            await state.set_state(None)
            await render_email_unlink_confirm(callback.bot, state, callback.message.chat.id, nav_action="replace")
        else:
            await state.set_state(EmailStates.waiting_email)
            await render_edit_email(callback.bot, state, callback.message.chat.id, nav_action="replace")
    elif previous.name in {SCREEN_EXPORT_STATUS, SCREEN_EXPORT_DONE}:
        await render_home(
            callback.bot,
            state,
            callback.message.chat.id,
            nav_action="replace",
            is_authed=profile is not None,
            profile=profile,
            tg_user=tg_user,
        )
    else:
        await render_home(
            callback.bot,
            state,
            callback.message.chat.id,
            nav_action="root",
            is_authed=profile is not None,
            profile=profile,
            tg_user=tg_user,
        )


@router.callback_query(F.data == "unknown.exit")
async def exit_unknown(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(None)
    profile = await load_active_profile(state)
    await render_home(
        callback.bot,
        state,
        callback.message.chat.id,
        nav_action="root",
        is_authed=profile is not None,
        profile=profile,
        tg_user=callback.from_user,
    )
