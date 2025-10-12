"""Callback handler for the help confirmation button."""

from __future__ import annotations

from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from .cmd_help import HELP_OK_CALLBACK

router = Router()


@router.callback_query(F.data == HELP_OK_CALLBACK)
async def handle_help_ok(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    try:
        await callback.bot.delete_message(chat_id, message_id)
    except TelegramBadRequest as error:
        if "message to delete not found" not in str(error).lower():
            raise
    await callback.answer()


__all__ = ["router", "handle_help_ok"]
