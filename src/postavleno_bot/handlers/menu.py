from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import datetime

import structlog
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from structlog.stdlib import BoundLogger

from ..core.logging import get_logger
from ..state.session import session_storage
from ..utils.safe_telegram import safe_delete, safe_edit, safe_send

MENU_ROUTER = Router(name="menu")

REFRESH_CALLBACK = "refresh_menu"
EXIT_CALLBACK = "exit_menu"


@contextmanager
def _action_logger(action: str, request_id: str) -> Iterator[BoundLogger]:
    structlog.contextvars.bind_contextvars(action=action)
    logger = get_logger(__name__).bind(action=action, request_id=request_id)
    try:
        yield logger
    finally:
        with suppress(LookupError):
            structlog.contextvars.unbind_contextvars("action")


def _format_timestamp(now: datetime | None = None) -> str:
    moment = now or datetime.now()
    return moment.strftime("%d.%m.%Y %H:%M")


def build_greeting_text(now: datetime | None = None) -> str:
    timestamp = _format_timestamp(now)
    return (
        "Привет! 👋 Меня зовут <b>Postavleno_Bot</b>\n"
        "Помогаю с поставками на Wildberries: следите за обновлениями и возвращайтесь к карточке в один клик.\n\n"
        "Используйте кнопки под сообщением, чтобы обновить карточку или выйти.\n\n"
        f"<i>Обновлено: {timestamp}</i>"
    )


def inline_controls() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=REFRESH_CALLBACK),
                InlineKeyboardButton(text="🚪 Выйти", callback_data=EXIT_CALLBACK),
            ]
        ]
    )


async def _render_card(
    *,
    bot: Bot,
    chat_id: int,
    text: str,
) -> int | None:
    inline_markup = inline_controls()
    last_message_id = await session_storage.get_last_message_id(chat_id)

    if last_message_id:
        edited = await safe_edit(
            bot,
            chat_id=chat_id,
            message_id=last_message_id,
            text=text,
            inline_markup=inline_markup,
        )
        if edited:
            await session_storage.set_last_message_id(chat_id, edited.message_id)
            return edited.message_id

    message = await safe_send(
        bot,
        chat_id=chat_id,
        text=text,
        reply_markup=inline_markup,
    )
    if not message:
        return None

    await session_storage.set_last_message_id(chat_id, message.message_id)

    if last_message_id and last_message_id != message.message_id:
        await safe_delete(bot, chat_id=chat_id, message_id=last_message_id)

    return message.message_id


@MENU_ROUTER.message(Command("start"))
async def handle_start(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    with _action_logger("start", request_id) as logger:
        logger.info("Получена команда /start")

        await safe_delete(bot, chat_id=message.chat.id, message_id=message.message_id)

        message_id = await _render_card(
            bot=bot,
            chat_id=message.chat.id,
            text=build_greeting_text(),
        )
        success = message_id is not None

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Главное меню показано", result="ok" if success else "fail", message_id=message_id
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.message()
async def handle_user_message(
    message: Message, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("user_message", request_id) as logger:
        logger.info("Получено сообщение пользователя", text=message.text)

        await safe_delete(bot, chat_id=message.chat.id, message_id=message.message_id)

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Сообщение пользователя удалено", result="ok")
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == REFRESH_CALLBACK)
async def handle_refresh(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("refresh", request_id) as logger:
        logger.info("Поступил запрос на обновление меню")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        message_id = await _render_card(
            bot=bot,
            chat_id=callback.message.chat.id,
            text=build_greeting_text(),
        )
        success = message_id is not None

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Меню обновлено", result="ok" if success else "fail", message_id=message_id)
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == EXIT_CALLBACK)
async def handle_exit(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("exit", request_id) as logger:
        logger.info("Поступил запрос на закрытие меню")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()

        chat_id = callback.message.chat.id
        message_id = callback.message.message_id

        await safe_delete(bot, chat_id=chat_id, message_id=message_id)
        await session_storage.clear(chat_id)

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Меню закрыто", result="ok")
        structlog.contextvars.unbind_contextvars("latency_ms")
