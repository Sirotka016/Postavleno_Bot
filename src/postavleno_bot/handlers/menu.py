from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
import structlog

from ..core.logging import get_logger
from ..keyboards.common import main_menu
from ..state.session import session_storage
from ..utils.safe_telegram import (
    safe_delete_message,
    safe_edit_message_text,
    safe_edit_reply_markup,
    safe_send_message,
)

MENU_ROUTER = Router(name="menu")

REFRESH_CALLBACK = "refresh_menu"
EXIT_CALLBACK = "exit_menu"


def _format_timestamp() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


def _main_card_text() -> str:
    return (
        "<b>Привет! 👋 Меня зовут Postavleno_Bot</b>\n"
        "Помогаю с поставками на Wildberries: подскажу, где что найти, покажу статус заказов и многое другое.\n\n"
        "Выберите действие на клавиатуре ниже. Нажмите <code>ℹ️ Помощь</code>, если что-то непонятно.\n\n"
        f"<i>Обновлено: {_format_timestamp()}</i>"
    )


def _help_card_text() -> str:
    return (
        "<b>Чем я могу помочь?</b>\n"
        "Я всегда рядом, чтобы подсказать: \n"
        "• Проверьте статус поставок через кнопку ‘🔎 Статус заказа’.\n"
        "• Изучайте доступные товары через ‘📦 Товары’.\n\n"
        "Если появятся вопросы или идеи — просто нажмите ‘🔄 Обновить’ или вернитесь через /start.\n\n"
        f"<i>Обновлено: {_format_timestamp()}</i>"
    )


def _status_card_text() -> str:
    return (
        "<b>🔎 Статус заказа</b>\n"
        "Совсем скоро я научусь показывать детали каждой поставки. Пока что следите за обновлениями — команда уже работает над интеграцией.\n\n"
        "Нажмите ‘🔄 Обновить’, чтобы вернуться к основному меню, или выберите другой раздел ниже.\n\n"
        f"<i>Обновлено: {_format_timestamp()}</i>"
    )


def _products_card_text() -> str:
    return (
        "<b>📦 Товары</b>\n"
        "В этом разделе появится каталог ваших позиций на Wildberries: остатки, цены и быстрые ссылки. Пожалуйста, загляните чуть позже — мы всё готовим.\n\n"
        "Можно обновить карточку или выбрать другой раздел на клавиатуре.\n\n"
        f"<i>Обновлено: {_format_timestamp()}</i>"
    )


def _inline_menu() -> InlineKeyboardMarkup:
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
    with_reply_keyboard: bool,
) -> Optional[int]:
    inline_markup = _inline_menu()
    last_message_id = await session_storage.get_last_message_id(chat_id)

    if last_message_id:
        edited = await safe_edit_message_text(
            bot,
            chat_id=chat_id,
            message_id=last_message_id,
            text=text,
            inline_markup=inline_markup,
        )
        if edited:
            await session_storage.set_last_message_id(chat_id, edited.message_id)
            return edited.message_id

    reply_markup = main_menu() if with_reply_keyboard else inline_markup
    message = await safe_send_message(
        bot,
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
    )
    if not message:
        return None

    if with_reply_keyboard:
        await safe_edit_reply_markup(bot, chat_id=chat_id, message_id=message.message_id, inline_markup=inline_markup)

    await session_storage.set_last_message_id(chat_id, message.message_id)

    if last_message_id and last_message_id != message.message_id:
        await safe_delete_message(bot, chat_id=chat_id, message_id=last_message_id)

    return message.message_id


@MENU_ROUTER.message(Command("start"))
async def handle_start(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    logger = get_logger(__name__).bind(action="start", request_id=request_id)
    logger.info("Получена команда /start")

    await safe_delete_message(bot, chat_id=message.chat.id, message_id=message.message_id)

    message_id = await _render_card(
        bot=bot,
        chat_id=message.chat.id,
        text=_main_card_text(),
        with_reply_keyboard=True,
    )
    success = message_id is not None

    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
    logger.info("Главное меню показано", result="ok" if success else "fail", message_id=message_id)
    structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.message(Command("help"))
async def handle_help(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    logger = get_logger(__name__).bind(action="help", request_id=request_id)
    logger.info("Получена команда /help")

    await safe_delete_message(bot, chat_id=message.chat.id, message_id=message.message_id)

    message_id = await _render_card(
        bot=bot,
        chat_id=message.chat.id,
        text=_help_card_text(),
        with_reply_keyboard=True,
    )
    success = message_id is not None

    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
    logger.info("Справка показана", result="ok" if success else "fail", message_id=message_id)
    structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.message(F.text == "ℹ️ Помощь")
async def handle_help_button(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    await handle_help(message, bot, request_id, started_at)


@MENU_ROUTER.message(F.text == "🔎 Статус заказа")
async def handle_status_button(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    logger = get_logger(__name__).bind(action="status", request_id=request_id)
    logger.info("Выбран раздел статуса заказа")

    await safe_delete_message(bot, chat_id=message.chat.id, message_id=message.message_id)
    message_id = await _render_card(
        bot=bot,
        chat_id=message.chat.id,
        text=_status_card_text(),
        with_reply_keyboard=True,
    )
    success = message_id is not None

    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
    logger.info("Карточка статуса показана", result="ok" if success else "fail", message_id=message_id)
    structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.message(F.text == "📦 Товары")
async def handle_products_button(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    logger = get_logger(__name__).bind(action="products", request_id=request_id)
    logger.info("Выбран раздел товаров")

    await safe_delete_message(bot, chat_id=message.chat.id, message_id=message.message_id)
    message_id = await _render_card(
        bot=bot,
        chat_id=message.chat.id,
        text=_products_card_text(),
        with_reply_keyboard=True,
    )
    success = message_id is not None

    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
    logger.info("Карточка товаров показана", result="ok" if success else "fail", message_id=message_id)
    structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.message()
async def handle_unknown_message(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    logger = get_logger(__name__).bind(action="unknown_text", request_id=request_id)
    logger.info("Получен произвольный текст", text=message.text)

    await safe_delete_message(bot, chat_id=message.chat.id, message_id=message.message_id)
    message_id = await _render_card(
        bot=bot,
        chat_id=message.chat.id,
        text=_main_card_text(),
        with_reply_keyboard=True,
    )
    success = message_id is not None

    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
    logger.info(
        "Карточка обновлена после произвольного текста",
        result="ok" if success else "fail",
        message_id=message_id,
    )
    structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == REFRESH_CALLBACK)
async def handle_refresh(callback: CallbackQuery, bot: Bot, request_id: str, started_at: float) -> None:
    logger = get_logger(__name__).bind(action="refresh", request_id=request_id)
    logger.info("Поступил запрос на обновление меню")

    if callback.message is None:
        await callback.answer()
        return

    await callback.answer(text="Меню обновлено ✨", show_alert=False)
    message_id = await _render_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=_main_card_text(),
        with_reply_keyboard=False,
    )
    success = message_id is not None

    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
    logger.info("Меню обновлено", result="ok" if success else "fail", message_id=message_id)
    structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == EXIT_CALLBACK)
async def handle_exit(callback: CallbackQuery, bot: Bot, request_id: str, started_at: float) -> None:
    logger = get_logger(__name__).bind(action="exit", request_id=request_id)
    logger.info("Поступил запрос на закрытие меню")

    if callback.message is None:
        await callback.answer()
        return

    await callback.answer(text="До встречи! 👋", show_alert=False)

    chat_id = callback.message.chat.id
    message_id = callback.message.message_id

    await safe_delete_message(bot, chat_id=chat_id, message_id=message_id)
    await session_storage.clear(chat_id)

    removal = await safe_send_message(
        bot,
        chat_id=chat_id,
        text="Меню скрыто. Чтобы вернуться, нажмите /start",
        reply_markup=ReplyKeyboardRemove(),
    )
    if removal:
        await safe_delete_message(bot, chat_id=chat_id, message_id=removal.message_id)

    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
    logger.info("Меню закрыто", result="ok")
    structlog.contextvars.unbind_contextvars("latency_ms")
