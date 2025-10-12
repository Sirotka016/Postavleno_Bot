"""State groups for conversational flows."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class LoginStates(StatesGroup):
    await_login = State()
    await_password = State()


class RegisterStates(StatesGroup):
    await_login = State()
    await_password = State()


class EditWBState(StatesGroup):
    await_token = State()


class EditCompanyState(StatesGroup):
    await_name = State()


class EditEmailState(StatesGroup):
    await_email = State()
    await_code = State()
