"""Handler for the /help command."""

from __future__ import annotations

from aiogram.filters import Command
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..ui.texts import help_message
from .utils import load_active_profile

router = Router()


def _resolve_name(message: Message, display_login: str | None) -> str:
    user = message.from_user
    if user:
        if user.username:
            return f"@{user.username}"
        if user.first_name:
            return user.first_name
        if user.full_name:
            return user.full_name
    return display_login or "друг"


@router.message(Command("help"))
async def handle_help(message: Message, state: FSMContext) -> None:
    profile = await load_active_profile(state)
    name = _resolve_name(message, profile.display_login if profile else None)
    text = help_message(name, authorized=profile is not None)
    await message.answer(text, disable_web_page_preview=True)


__all__ = ["router"]
