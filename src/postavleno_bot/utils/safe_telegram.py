from __future__ import annotations

from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
import structlog


_NOT_MODIFIED_SUBSTRING = "message is not modified"


def _is_not_modified_error(error: TelegramBadRequest) -> bool:
    """Return ``True`` if Telegram reports that message is not modified."""

    message = str(error)
    return _NOT_MODIFIED_SUBSTRING in message.lower()


async def safe_send(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | InlineKeyboardMarkup | None = None,
) -> Optional[Message]:
    logger = structlog.get_logger(__name__).bind(action="send_message")
    try:
        result = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            disable_notification=True,
            disable_web_page_preview=True,
            parse_mode="HTML",
        )
        return result
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        logger.warning("Не удалось отправить сообщение", error=str(error))
        return None


async def safe_edit(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    *,
    inline_markup: InlineKeyboardMarkup | None = None,
) -> Optional[Message]:
    logger = structlog.get_logger(__name__).bind(action="edit_message")
    try:
        result = await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=inline_markup,
            parse_mode="HTML",
        )
        if isinstance(result, Message):
            return result
        return None
    except TelegramBadRequest as error:
        if _is_not_modified_error(error):
            logger.debug("Сообщение не изменилось")
            return None
        logger.warning("Не удалось изменить сообщение", error=str(error))
        return None
    except TelegramForbiddenError as error:
        logger.warning("Не удалось изменить сообщение", error=str(error))
        return None


async def safe_delete(bot: Bot, chat_id: int, message_id: int) -> bool:
    logger = structlog.get_logger(__name__).bind(action="delete_message")
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        logger.warning("Не удалось удалить сообщение", error=str(error))
        return False
