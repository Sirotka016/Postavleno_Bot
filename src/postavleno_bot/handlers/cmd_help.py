"""Handler for the /help command."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..ui.texts import help_message
from .utils import load_active_profile

router = Router()

HELP_OK_CALLBACK = "help.ok"
HELP_OK_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Понятно", callback_data=HELP_OK_CALLBACK)]]
)


def _resolve_name(message: Message, display_login: str | None) -> str:
    user = message.from_user
    if user:
        username = (user.username or "").strip()
        if username:
            return f"@{username}"
        first_name = (user.first_name or "").strip()
        if first_name:
            return first_name
    return display_login or "друг"


@router.message(Command("help"))
async def handle_help(message: Message, state: FSMContext) -> None:
    profile = await load_active_profile(state)
    name = _resolve_name(message, profile.display_login if profile else None)
    text = help_message(name, authorized=profile is not None)
    await message.answer(
        text,
        disable_web_page_preview=True,
        reply_markup=HELP_OK_KEYBOARD,
    )


__all__ = ["router", "HELP_OK_CALLBACK", "HELP_OK_KEYBOARD", "handle_help"]
