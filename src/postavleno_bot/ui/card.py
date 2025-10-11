"""Utilities for rendering a single card message per chat."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext


class CardManager:
    """Keep track of the latest bot message in each chat."""

    def __init__(self) -> None:
        self._message_ids: dict[int, int] = {}

    async def render(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        *,
        reply_markup: Any = None,
        state: FSMContext | None = None,
    ) -> int:
        message_id = self._message_ids.get(chat_id)
        if message_id:
            try:
                message = await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True,
                )
                new_id = message.message_id if hasattr(message, "message_id") else message_id
                self._message_ids[chat_id] = new_id
                if state is not None:
                    await state.update_data(card_message_id=new_id)
                return new_id
            except TelegramBadRequest:
                pass

        previous_id = message_id
        message = await bot.send_message(
            chat_id,
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        new_id = message.message_id
        self._message_ids[chat_id] = new_id
        if state is not None:
            await state.update_data(card_message_id=new_id)
        if previous_id and previous_id != new_id:
            with suppress(TelegramBadRequest):
                await bot.delete_message(chat_id, previous_id)
        return new_id


card_manager = CardManager()

__all__ = ["card_manager", "CardManager"]
