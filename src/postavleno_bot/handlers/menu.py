from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
import structlog
from structlog.stdlib import BoundLogger

from ..core.logging import get_logger
from ..keyboards.common import main_menu
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
        try:
            structlog.contextvars.unbind_contextvars("action")
        except LookupError:
            pass


def _format_timestamp(now: datetime | None = None) -> str:
    moment = now or datetime.now()
    return moment.strftime("%d.%m.%Y %H:%M")


def build_greeting_text(now: datetime | None = None) -> str:
    timestamp = _format_timestamp(now)
    return (
        "Привет! 👋 Меня зовут <b>Postavleno_Bot</b>\n"
        "Помогаю с поставками на Wildberries: подскажу, где что найти, проверю статусы и многое другое.\n\n"
        "Выберите действие на клавиатуре ниже. Если что-то непонятно — нажмите «ℹ️ Помощь».\n\n"
        f"<i>Обновлено: {timestamp}</i>"
    )


def build_help_text(now: datetime | None = None) -> str:
    timestamp = _format_timestamp(now)
    return (
        "<b>ℹ️ Помощь</b>\n"
        "Здесь вы найдёте быстрые ответы: \n"
        "• «🔎 Статус заказа» — следите за поставками и будущими отгрузками.\n"
        "• «📦 Товары» — скоро появится каталог с остатками и ценами.\n\n"
        "Возвращайтесь в главное меню через «🔄 Обновить» или команду /start.\n\n"
        f"<i>Обновлено: {timestamp}</i>"
    )


def build_status_text(now: datetime | None = None) -> str:
    timestamp = _format_timestamp(now)
    return (
        "<b>🔎 Статус заказа</b>\n"
        "Совсем скоро я научусь показывать прогресс каждой поставки. Следите за обновлениями — команда уже работает над интеграцией.\n\n"
        "Нажмите «🔄 Обновить», чтобы вернуться к карточке, или выберите другой раздел.\n\n"
        f"<i>Обновлено: {timestamp}</i>"
    )


def build_products_text(now: datetime | None = None) -> str:
    timestamp = _format_timestamp(now)
    return (
        "<b>📦 Товары</b>\n"
        "Здесь появится каталог ваших позиций на Wildberries: остатки, цены и быстрые ссылки. Пожалуйста, загляните позже — мы всё готовим.\n\n"
        "Можно обновить карточку или сразу выбрать другой раздел на клавиатуре.\n\n"
        f"<i>Обновлено: {timestamp}</i>"
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

    reply_markup = main_menu() if with_reply_keyboard else inline_markup
    message = await safe_send(
        bot,
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
    )
    if not message:
        return None

    await session_storage.set_last_message_id(chat_id, message.message_id)

    if with_reply_keyboard:
        await safe_edit(
            bot,
            chat_id=chat_id,
            message_id=message.message_id,
            text=text,
            inline_markup=inline_markup,
        )

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
            with_reply_keyboard=True,
        )
        success = message_id is not None

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Главное меню показано", result="ok" if success else "fail", message_id=message_id)
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.message(Command("help"))
async def handle_help(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    with _action_logger("help", request_id) as logger:
        logger.info("Получена команда /help")

        await safe_delete(bot, chat_id=message.chat.id, message_id=message.message_id)

        message_id = await _render_card(
            bot=bot,
            chat_id=message.chat.id,
            text=build_help_text(),
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
    with _action_logger("status", request_id) as logger:
        logger.info("Выбран раздел статуса заказа")

        await safe_delete(bot, chat_id=message.chat.id, message_id=message.message_id)
        message_id = await _render_card(
            bot=bot,
            chat_id=message.chat.id,
            text=build_status_text(),
            with_reply_keyboard=True,
        )
        success = message_id is not None

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Карточка статуса показана", result="ok" if success else "fail", message_id=message_id)
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.message(F.text == "📦 Товары")
async def handle_products_button(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    with _action_logger("products", request_id) as logger:
        logger.info("Выбран раздел товаров")

        await safe_delete(bot, chat_id=message.chat.id, message_id=message.message_id)
        message_id = await _render_card(
            bot=bot,
            chat_id=message.chat.id,
            text=build_products_text(),
            with_reply_keyboard=True,
        )
        success = message_id is not None

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Карточка товаров показана", result="ok" if success else "fail", message_id=message_id)
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.message()
async def handle_unknown_message(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    with _action_logger("unknown_text", request_id) as logger:
        logger.info("Получен произвольный текст", text=message.text)

        await safe_delete(bot, chat_id=message.chat.id, message_id=message.message_id)
        message_id = await _render_card(
            bot=bot,
            chat_id=message.chat.id,
            text=build_greeting_text(),
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
    with _action_logger("refresh", request_id) as logger:
        logger.info("Поступил запрос на обновление меню")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer(text="Меню обновлено ✨", show_alert=False)
        message_id = await _render_card(
            bot=bot,
            chat_id=callback.message.chat.id,
            text=build_greeting_text(),
            with_reply_keyboard=False,
        )
        success = message_id is not None

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Меню обновлено", result="ok" if success else "fail", message_id=message_id)
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == EXIT_CALLBACK)
async def handle_exit(callback: CallbackQuery, bot: Bot, request_id: str, started_at: float) -> None:
    with _action_logger("exit", request_id) as logger:
        logger.info("Поступил запрос на закрытие меню")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer(text="До встречи! 👋", show_alert=False)

        chat_id = callback.message.chat.id
        message_id = callback.message.message_id

        await safe_delete(bot, chat_id=chat_id, message_id=message_id)
        await session_storage.clear(chat_id)

        removal = await safe_send(
            bot,
            chat_id=chat_id,
            text="Меню скрыто. Чтобы вернуться, нажмите /start",
            reply_markup=ReplyKeyboardRemove(),
        )
        if removal:
            await safe_delete(bot, chat_id=chat_id, message_id=removal.message_id)

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Меню закрыто", result="ok")
        structlog.contextvars.unbind_contextvars("latency_ms")
