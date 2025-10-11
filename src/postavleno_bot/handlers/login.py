"""Handlers for the login flow."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..domain import validate_login
from ..services.accounts import AccountNotFoundError, get_accounts_repo
from ..state import LoginStates
from .pages import render_login, render_login_error, render_profile
from .utils import delete_user_message, set_auth_user

router = Router()


@router.callback_query(F.data == "login.retry")
async def retry_login(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(LoginStates.await_login)
    await render_login(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.message(LoginStates.await_login)
async def handle_login_input(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    login_text = (message.text or "").strip()
    if not validate_login(login_text):
        await render_login(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            prompt="Логин должен содержать 3–32 символа латиницы, цифр, . _ -",
        )
        return
    await state.update_data(login_candidate=login_text, login_normalized=login_text.lower())
    await state.set_state(LoginStates.await_password)
    await render_login(
        message.bot,
        state,
        message.chat.id,
        nav_action="replace",
        await_password=True,
    )


@router.message(LoginStates.await_password)
async def handle_password_input(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    data = await state.get_data()
    login_normalized = str(data.get("login_normalized") or "").strip()
    if not login_normalized:
        await state.set_state(LoginStates.await_login)
        await render_login(message.bot, state, message.chat.id, nav_action="replace")
        return
    password = message.text or ""
    repo = get_accounts_repo()
    try:
        profile = repo.get(login_normalized)
    except AccountNotFoundError:
        await state.set_state(LoginStates.await_login)
        await render_login_error(message.bot, state, message.chat.id)
        return
    if not repo.verify_password(profile, password):
        await state.set_state(LoginStates.await_login)
        await render_login_error(message.bot, state, message.chat.id)
        return
    await set_auth_user(state, profile.username)
    await state.set_state(None)
    await state.update_data(login_candidate=None, login_normalized=None)
    await render_profile(message.bot, state, message.chat.id, profile, nav_action="replace")
