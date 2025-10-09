from __future__ import annotations

import binascii
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import datetime

import structlog
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from structlog.stdlib import BoundLogger

from ..core.config import get_settings
from ..core.logging import get_logger
from ..integrations.wb_client import WBApiError, WBAuthError, WBRatelimitError, WBStockItem
from ..services.stocks import (
    WarehouseSummary,
    filter_by_warehouse,
    get_stock_data,
    summarize_by_warehouse,
)
from ..state.session import session_storage
from ..utils.safe_telegram import safe_delete, safe_edit, safe_send

MENU_ROUTER = Router(name="menu")

MAIN_REFRESH_CALLBACK = "main.refresh"
MAIN_EXIT_CALLBACK = "main.exit"
MAIN_STOCKS_CALLBACK = "main.stocks"

STOCKS_OPEN_CALLBACK = "stocks.open"
STOCKS_VIEW_CALLBACK = "stocks.view"
STOCKS_REFRESH_CALLBACK = "stocks.refresh"
STOCKS_BACK_CALLBACK = "stocks.back"
STOCKS_FILTER_PREFIX = "stocks.filter:"
STOCKS_FILTER_ALL = f"{STOCKS_FILTER_PREFIX}ALL"
WAREHOUSE_KEY_PREFIX = "wh:"
MAX_LINES = 40


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
        "Нажмите «📦 Остатки WB», чтобы увидеть остатки на складах Wildberries.\n\n"
        "Используйте кнопки под сообщением, чтобы обновить карточку или выйти.\n\n"
        f"<i>Обновлено: {timestamp}</i>"
    )


def build_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Остатки WB", callback_data=MAIN_STOCKS_CALLBACK)],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=MAIN_REFRESH_CALLBACK),
                InlineKeyboardButton(text="🚪 Выйти", callback_data=MAIN_EXIT_CALLBACK),
            ],
        ]
    )


def inline_controls() -> InlineKeyboardMarkup:
    return build_main_keyboard()


def build_stocks_menu_text(now: datetime | None = None) -> str:
    timestamp = _format_timestamp(now)
    return (
        "<b>📦 Остатки на складах WB</b>\n\n"
        "Здесь можно выгрузить актуальные остатки по складам Wildberries.\n"
        "Нажмите «👀 Посмотреть остатки», чтобы увидеть список складов.\n\n"
        f"<i>Обновлено: {timestamp}</i>"
    )


def build_stocks_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👀 Посмотреть остатки", callback_data=STOCKS_VIEW_CALLBACK
                )
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=STOCKS_REFRESH_CALLBACK),
                InlineKeyboardButton(text="⬅️ Назад", callback_data=STOCKS_BACK_CALLBACK),
            ],
            [InlineKeyboardButton(text="🚪 Выйти", callback_data=MAIN_EXIT_CALLBACK)],
        ]
    )


def build_missing_token_text() -> str:
    return (
        "<b>📦 Остатки на складах WB</b>\n\n"
        "Добавьте <code>WB_API_TOKEN</code> в .env, токен категории Statistics, чтобы выгружать остатки."
    )


def build_missing_token_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=STOCKS_BACK_CALLBACK)],
            [InlineKeyboardButton(text="🚪 Выйти", callback_data=MAIN_EXIT_CALLBACK)],
        ]
    )


def build_rate_limit_text(retry_after: int | None) -> str:
    suffix = f" через {retry_after} секунд" if retry_after else " чуть позже"
    return (
        "<b>📦 Остатки на складах WB</b>\n\n"
        "Лимит Wildberries на обновление превышен. Попробуйте обновить карточку"
        f"{suffix}."
    )


def build_auth_error_text() -> str:
    return (
        "<b>📦 Остатки на складах WB</b>\n\n"
        "Токен WB отклонён. Проверьте категорию “Statistics” и срок действия."
    )


def build_error_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=STOCKS_REFRESH_CALLBACK),
                InlineKeyboardButton(text="⬅️ Назад", callback_data=STOCKS_BACK_CALLBACK),
            ],
            [InlineKeyboardButton(text="🚪 Выйти", callback_data=MAIN_EXIT_CALLBACK)],
        ]
    )


def build_warehouses_keyboard(
    summaries: list[WarehouseSummary],
) -> tuple[InlineKeyboardMarkup, dict[str, str]]:
    inline_keyboard: list[list[InlineKeyboardButton]] = []
    mapping: dict[str, str] = {}

    inline_keyboard.append(
        [InlineKeyboardButton(text="🧾 Все склады", callback_data=STOCKS_FILTER_ALL)]
    )

    for summary in summaries:
        code = _warehouse_code(summary.name)
        mapping[code] = summary.name
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=summary.name,
                    callback_data=f"{STOCKS_FILTER_PREFIX}{code}",
                )
            ]
        )

    inline_keyboard.append(
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=STOCKS_REFRESH_CALLBACK),
            InlineKeyboardButton(text="⬅️ Назад", callback_data=STOCKS_BACK_CALLBACK),
        ]
    )
    inline_keyboard.append(
        [InlineKeyboardButton(text="🚪 Выйти", callback_data=MAIN_EXIT_CALLBACK)]
    )

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard), mapping


def build_warehouses_text(
    summaries: list[WarehouseSummary],
    *,
    total_items: int,
    now: datetime | None = None,
) -> str:
    timestamp = _format_timestamp(now)
    if not summaries:
        return (
            "<b>🏬 Склады с остатками</b>\n"
            "Сейчас нет остатков на складах WB.\n\n"
            f"<i>Обновлено: {timestamp}</i>"
        )

    lines = [
        f"• {summary.name} — {summary.total_qty} шт., {summary.sku_count} SKU"
        for summary in summaries
    ]
    body = "\n".join(lines)
    return (
        "<b>🏬 Склады с остатками</b>\n"
        f"{body}\n\n"
        "Выберите склад ниже, либо «🧾 Все склады».\n"
        f"<i>Позиций всего: {total_items}, обновлено: {timestamp}</i>"
    )


def build_stocks_details_text(
    items: list[WBStockItem],
    *,
    title: str,
    now: datetime | None = None,
) -> str:
    timestamp = _format_timestamp(now)
    if not items:
        return (
            f"<b>📦 Остатки — {title}</b>\n"
            "Сейчас нет остатков на складах WB.\n\n"
            f"<i>Обновлено: {timestamp}</i>"
        )

    sorted_items = sorted(
        items,
        key=lambda item: (-item.quantity, (item.supplierArticle or ""), item.nmId),
    )
    total = len(sorted_items)
    limited = sorted_items[:MAX_LINES]
    lines = [
        f"• {item.supplierArticle or '—'} (nm:{item.nmId}) — {item.quantity} шт. — {item.warehouseName}"
        for item in limited
    ]
    body = "\n".join(lines)
    extra = f"\n\nПоказаны первые {MAX_LINES} из {total} позиций" if total > MAX_LINES else ""
    return f"<b>📦 Остатки — {title}</b>\n" f"{body}{extra}\n\n" f"<i>Обновлено: {timestamp}</i>"


def _warehouse_code(name: str) -> str:
    checksum = binascii.crc32(name.encode("utf-8")) & 0xFFFFFFFF
    return f"{WAREHOUSE_KEY_PREFIX}{checksum:08x}"


async def _render_card(
    *,
    bot: Bot,
    chat_id: int,
    text: str,
    inline_markup: InlineKeyboardMarkup,
) -> int | None:
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


async def _render_main_menu(bot: Bot, chat_id: int) -> int | None:
    await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={})
    return await _render_card(
        bot=bot,
        chat_id=chat_id,
        text=build_greeting_text(),
        inline_markup=build_main_keyboard(),
    )


def _calc_latency(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


@MENU_ROUTER.message(Command("start"))
async def handle_start(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    with _action_logger("start", request_id) as logger:
        logger.info("Получена команда /start")

        await safe_delete(bot, chat_id=message.chat.id, message_id=message.message_id)

        message_id = await _render_main_menu(bot, message.chat.id)
        success = message_id is not None

        latency_ms = _calc_latency(started_at)
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

        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Сообщение пользователя удалено", result="ok")
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == MAIN_REFRESH_CALLBACK)
async def handle_refresh(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("refresh", request_id) as logger:
        logger.info("Поступил запрос на обновление меню")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        message_id = await _render_main_menu(bot, callback.message.chat.id)
        success = message_id is not None

        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Меню обновлено", result="ok" if success else "fail", message_id=message_id)
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == MAIN_EXIT_CALLBACK)
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

        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Меню закрыто", result="ok")
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data in {MAIN_STOCKS_CALLBACK, STOCKS_OPEN_CALLBACK})
async def handle_stocks_open(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("stocks_open", request_id) as logger:
        logger.info("Переход в раздел остатков")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()

        chat_id = callback.message.chat.id
        settings = get_settings()
        token_secret = settings.wb_api_token
        if token_secret is None:
            message_id = await _render_card(
                bot=bot,
                chat_id=chat_id,
                text=build_missing_token_text(),
                inline_markup=build_missing_token_keyboard(),
            )
            await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={})
        else:
            message_id = await _render_card(
                bot=bot,
                chat_id=chat_id,
                text=build_stocks_menu_text(),
                inline_markup=build_stocks_menu_keyboard(),
            )
            await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={})

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Раздел остатков открыт", result="ok" if success else "fail", message_id=message_id
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


async def _load_stocks(token: str, *, force_refresh: bool) -> list[WBStockItem]:
    return await get_stock_data(token, force_refresh=force_refresh)


def _build_error_response(error: Exception) -> tuple[str, InlineKeyboardMarkup]:
    if isinstance(error, WBAuthError):
        return build_auth_error_text(), build_error_keyboard()
    if isinstance(error, WBRatelimitError):
        return build_rate_limit_text(error.retry_after), build_error_keyboard()
    return (
        "<b>📦 Остатки на складах WB</b>\n\n"
        "Не удалось получить остатки. Попробуйте обновить карточку позже.",
        build_error_keyboard(),
    )


@MENU_ROUTER.callback_query(lambda c: c.data == STOCKS_VIEW_CALLBACK)
async def handle_stocks_view(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("stocks_view", request_id) as logger:
        logger.info("Запрошен список складов")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        chat_id = callback.message.chat.id

        settings = get_settings()
        token_secret = settings.wb_api_token
        if token_secret is None:
            text = build_missing_token_text()
            keyboard = build_missing_token_keyboard()
            message_id = await _render_card(
                bot=bot, chat_id=chat_id, text=text, inline_markup=keyboard
            )
            await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={})
        else:
            token = token_secret.get_secret_value()
            try:
                items = await _load_stocks(token, force_refresh=False)
            except WBApiError as error:
                text, keyboard = _build_error_response(error)
                message_id = await _render_card(
                    bot=bot,
                    chat_id=chat_id,
                    text=text,
                    inline_markup=keyboard,
                )
                await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={})
            else:
                summaries = summarize_by_warehouse(items)
                keyboard, mapping = build_warehouses_keyboard(summaries)
                text = build_warehouses_text(summaries, total_items=len(items))
                message_id = await _render_card(
                    bot=bot,
                    chat_id=chat_id,
                    text=text,
                    inline_markup=keyboard,
                )
                await session_storage.update_session(
                    chat_id, stocks_view="summary", stocks_wh_map=mapping
                )
                logger = logger.bind(warehouses_count=len(summaries), items_count=len(items))

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Список складов показан", result="ok" if success else "fail", message_id=message_id
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


async def _render_stock_filter(
    *,
    bot: Bot,
    chat_id: int,
    items: list[WBStockItem],
    warehouse_name: str | None,
) -> tuple[int | None, dict[str, object]]:
    filtered_items = filter_by_warehouse(items, warehouse_name)
    title = warehouse_name or "Все склады"
    text = build_stocks_details_text(filtered_items, title=title)
    keyboard, mapping = build_warehouses_keyboard(summarize_by_warehouse(items))
    message_id = await _render_card(bot=bot, chat_id=chat_id, text=text, inline_markup=keyboard)
    await session_storage.update_session(
        chat_id,
        stocks_view="all" if warehouse_name is None else _warehouse_code(warehouse_name),
        stocks_wh_map=mapping,
    )
    metadata: dict[str, object] = {
        "view": "all" if warehouse_name is None else "wh",
        "warehouse": warehouse_name,
        "items_count": len(filtered_items),
        "warehouses_count": len(mapping),
    }
    return message_id, metadata


@MENU_ROUTER.callback_query(lambda c: c.data == STOCKS_REFRESH_CALLBACK)
async def handle_stocks_refresh(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("stocks_refresh", request_id) as logger:
        logger.info("Запрошено обновление раздела остатков")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        chat_id = callback.message.chat.id
        session = await session_storage.get_session(chat_id)

        settings = get_settings()
        token_secret = settings.wb_api_token
        if token_secret is None:
            text = build_missing_token_text()
            keyboard = build_missing_token_keyboard()
            message_id = await _render_card(
                bot=bot, chat_id=chat_id, text=text, inline_markup=keyboard
            )
            await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={})
        else:
            mapping = session.stocks_wh_map
            current_view = session.stocks_view

            if current_view is None and not mapping:
                message_id = await _render_card(
                    bot=bot,
                    chat_id=chat_id,
                    text=build_stocks_menu_text(),
                    inline_markup=build_stocks_menu_keyboard(),
                )
                await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={})
            else:
                token = token_secret.get_secret_value()
                try:
                    items = await _load_stocks(token, force_refresh=True)
                except WBApiError as error:
                    text, keyboard = _build_error_response(error)
                    message_id = await _render_card(
                        bot=bot,
                        chat_id=chat_id,
                        text=text,
                        inline_markup=keyboard,
                    )
                    await session_storage.update_session(
                        chat_id, stocks_view=None, stocks_wh_map={}
                    )
                else:
                    if current_view in {None, "summary"}:
                        summaries = summarize_by_warehouse(items)
                        keyboard, mapping = build_warehouses_keyboard(summaries)
                        text = build_warehouses_text(summaries, total_items=len(items))
                        await session_storage.update_session(
                            chat_id, stocks_view="summary", stocks_wh_map=mapping
                        )
                        message_id = await _render_card(
                            bot=bot,
                            chat_id=chat_id,
                            text=text,
                            inline_markup=keyboard,
                        )
                        logger = logger.bind(
                            warehouses_count=len(summaries), items_count=len(items)
                        )
                    elif current_view == "all":
                        message_id, metadata = await _render_stock_filter(
                            bot=bot,
                            chat_id=chat_id,
                            items=items,
                            warehouse_name=None,
                        )
                        logger = logger.bind(**metadata)
                    elif current_view and current_view.startswith(WAREHOUSE_KEY_PREFIX):
                        warehouse_name = mapping.get(current_view)
                        message_id, metadata = await _render_stock_filter(
                            bot=bot,
                            chat_id=chat_id,
                            items=items,
                            warehouse_name=warehouse_name,
                        )
                        logger = logger.bind(**metadata)
                    else:
                        summaries = summarize_by_warehouse(items)
                        keyboard, mapping = build_warehouses_keyboard(summaries)
                        text = build_warehouses_text(summaries, total_items=len(items))
                        await session_storage.update_session(
                            chat_id, stocks_view="summary", stocks_wh_map=mapping
                        )
                        message_id = await _render_card(
                            bot=bot,
                            chat_id=chat_id,
                            text=text,
                            inline_markup=keyboard,
                        )
                        logger = logger.bind(
                            warehouses_count=len(summaries), items_count=len(items)
                        )

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Раздел остатков обновлён", result="ok" if success else "fail", message_id=message_id
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == STOCKS_BACK_CALLBACK)
async def handle_stocks_back(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("stocks_back", request_id) as logger:
        logger.info("Возврат в главное меню из остатков")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        chat_id = callback.message.chat.id
        message_id = await _render_main_menu(bot, chat_id)

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Возвращение в главное меню", result="ok" if success else "fail", message_id=message_id
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data and c.data.startswith(STOCKS_FILTER_PREFIX))
async def handle_stocks_filter(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("stocks_filter", request_id) as logger:
        logger.info("Выбран фильтр склада", filter_data=callback.data)

        if callback.message is None or callback.data is None:
            await callback.answer()
            return

        await callback.answer()
        chat_id = callback.message.chat.id
        filter_value = callback.data[len(STOCKS_FILTER_PREFIX) :]

        settings = get_settings()
        token_secret = settings.wb_api_token
        if token_secret is None:
            text = build_missing_token_text()
            keyboard = build_missing_token_keyboard()
            message_id = await _render_card(
                bot=bot, chat_id=chat_id, text=text, inline_markup=keyboard
            )
            await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={})
        else:
            token = token_secret.get_secret_value()
            try:
                items = await _load_stocks(token, force_refresh=False)
            except WBApiError as error:
                text, keyboard = _build_error_response(error)
                message_id = await _render_card(
                    bot=bot,
                    chat_id=chat_id,
                    text=text,
                    inline_markup=keyboard,
                )
                await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={})
            else:
                session = await session_storage.get_session(chat_id)
                mapping = session.stocks_wh_map
                warehouse_name = None if filter_value == "ALL" else mapping.get(filter_value)
                message_id, metadata = await _render_stock_filter(
                    bot=bot,
                    chat_id=chat_id,
                    items=items,
                    warehouse_name=warehouse_name,
                )
                logger = logger.bind(**metadata)

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Фильтр складов обработан", result="ok" if success else "fail", message_id=message_id
        )
        structlog.contextvars.unbind_contextvars("latency_ms")
