"""Handlers for the registration flow."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..domain import validate_login
from ..services.accounts import AccountAlreadyExistsError, get_accounts_repo
from ..state import RegisterStates
from .pages import render_profile, render_register, render_register_taken
from .utils import delete_user_message, set_auth_user

router = Router()


@router.callback_query(F.data == "register.retry")
async def retry_register(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(RegisterStates.await_login)
    await render_register(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.message(RegisterStates.await_login)
async def handle_register_login(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    login_text = (message.text or "").strip()
    if not validate_login(login_text):
        await render_register(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            prompt="Логин должен содержать 3–32 символа латиницы, цифр, . _ -",
        )
        return
    repo = get_accounts_repo()
    if repo.exists(login_text.lower()):
        await render_register_taken(message.bot, state, message.chat.id)
        return
    await state.update_data(register_login=login_text, register_normalized=login_text.lower())
    await state.set_state(RegisterStates.await_password)
    await render_register(
        message.bot,
        state,
        message.chat.id,
        nav_action="replace",
        await_password=True,
    )


@router.message(RegisterStates.await_password)
async def handle_register_password(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    data = await state.get_data()
    login_text = str(data.get("register_login") or "").strip()
    if not login_text:
        await state.set_state(RegisterStates.await_login)
        await render_register(message.bot, state, message.chat.id, nav_action="replace")
        return
    password = (message.text or "").strip()
    if len(password) < 6:
        await render_register(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            await_password=True,
            prompt="Пароль должен содержать не менее 6 символов.",
        )
        return
    repo = get_accounts_repo()
    try:
        profile = repo.create(display_login=login_text, password=password)
    except AccountAlreadyExistsError:
        await state.set_state(RegisterStates.await_login)
        await render_register_taken(message.bot, state, message.chat.id)
        return
    await set_auth_user(state, profile.username)
    await state.set_state(None)
    await state.update_data(register_login=None, register_normalized=None)
    await render_profile(message.bot, state, message.chat.id, profile, nav_action="replace")
