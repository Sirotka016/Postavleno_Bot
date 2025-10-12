"""State groups for conversational flows."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class LoginStates(StatesGroup):
    await_login = State()
    await_password = State()


class RegisterStates(StatesGroup):
    await_login = State()
    await_password = State()


class CompanyStates(StatesGroup):
    waiting_name = State()


class EmailStates(StatesGroup):
    waiting_email = State()
    waiting_code = State()


class WbStates(StatesGroup):
    waiting_token = State()
