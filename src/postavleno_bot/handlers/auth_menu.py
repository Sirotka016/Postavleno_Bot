"""Handlers for the authorization menu."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from ..state import LoginStates, RegisterStates
from .pages import render_login, render_register

router = Router()


@router.callback_query(F.data == "auth.login")
async def start_login(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(LoginStates.await_login)
    await state.update_data(login_input=None)
    await render_login(callback.bot, state, callback.message.chat.id, nav_action="push")


@router.callback_query(F.data == "auth.register")
async def start_register(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(RegisterStates.await_login)
    await state.update_data(register_login=None)
    await render_register(callback.bot, state, callback.message.chat.id, nav_action="push")
