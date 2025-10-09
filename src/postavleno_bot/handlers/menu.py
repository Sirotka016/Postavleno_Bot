from __future__ import annotations

import binascii
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import datetime

import structlog
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from structlog.stdlib import BoundLogger

from ..core.config import get_settings
from ..core.logging import get_logger
from ..integrations.wb_client import WBApiError, WBAuthError, WBRatelimitError, WBStockItem
from ..services.stocks import (
    TELEGRAM_TEXT_LIMIT,
    PagedView,
    WarehouseSummary,
    build_export_csv,
    build_export_filename,
    build_pages_grouped_by_warehouse,
    format_single_warehouse,
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
STOCKS_EXPORT_CALLBACK = "stocks.export"
STOCKS_FILTER_PREFIX = "stocks.filter:"
STOCKS_FILTER_ALL = f"{STOCKS_FILTER_PREFIX}ALL"
STOCKS_PAGE_PREFIX = "stocks.page:"
WAREHOUSE_KEY_PREFIX = "wh:"


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


def _build_warehouse_mapping(summaries: list[WarehouseSummary]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for summary in summaries:
        mapping[_warehouse_code(summary.name)] = summary.name
    return mapping


def page_buttons(current: int, total: int) -> list[list[InlineKeyboardButton]]:
    if total <= 1:
        return []

    numbers: list[int]
    if total <= 9:
        numbers = list(range(1, total + 1))
    else:
        numbers = [1]
        start = max(2, current - 2)
        end = min(total - 1, current + 2)
        for number in range(start, end + 1):
            if number not in numbers:
                numbers.append(number)
        if total not in numbers:
            numbers.append(total)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for number in numbers:
        row.append(
            InlineKeyboardButton(text=str(number), callback_data=f"{STOCKS_PAGE_PREFIX}{number}")
        )
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def build_stock_results_keyboard(*, total_pages: int, current_page: int) -> InlineKeyboardMarkup:
    inline_keyboard: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="⬇️ Выгрузить", callback_data=STOCKS_EXPORT_CALLBACK)]
    ]

    inline_keyboard.extend(page_buttons(current_page, total_pages))

    inline_keyboard.append(
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=STOCKS_REFRESH_CALLBACK),
            InlineKeyboardButton(text="⬅️ Назад", callback_data=STOCKS_BACK_CALLBACK),
        ]
    )
    inline_keyboard.append(
        [InlineKeyboardButton(text="🚪 Выйти", callback_data=MAIN_EXIT_CALLBACK)]
    )

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def _clamp_page(page: int, total_pages: int) -> int:
    if total_pages <= 0:
        return 1
    return max(1, min(page, total_pages))


def _get_page_lines(paged_view: PagedView, page: int) -> tuple[list[str], int]:
    total_pages = paged_view.total_pages or len(paged_view.pages)
    total_pages = max(total_pages, 1)
    page_number = _clamp_page(page, total_pages)
    if not paged_view.pages:
        return [], page_number
    index = min(page_number - 1, len(paged_view.pages) - 1)
    return paged_view.pages[index].lines, page_number


def build_all_view_text(
    *,
    summaries: list[WarehouseSummary],
    paged_view: PagedView,
    current_page: int,
    now: datetime | None = None,
) -> tuple[str, int, int]:
    timestamp = _format_timestamp(now)
    warehouses_count = len(summaries)

    if warehouses_count == 0:
        text = (
            "<b>🏬 Склады с остатками</b>\n"
            "Сейчас нет остатков на складах WB.\n\n"
            f"<i>Всего позиций: 0. Обновлено: {timestamp}</i>"
        )
        return text, 0, 1

    total_pages = paged_view.total_pages or len(paged_view.pages) or 1
    lines, page_number = _get_page_lines(paged_view, current_page)
    details = "\n".join(lines) if lines else "Нет позиций для отображения."
    summary_lines = [
        f"• {summary.name} — {summary.total_qty} шт., {summary.sku_count} SKU"
        for summary in summaries
    ]
    summary_block = "\n".join(summary_lines)

    text = (
        "<b>🏬 Склады с остатками</b>\n"
        f"{summary_block}\n\n"
        f"<b>📄 Страница {page_number}/{total_pages}</b>\n"
        f"{details}\n\n"
        f"<i>Всего позиций: {paged_view.total_items}. Обновлено: {timestamp}</i>"
    )

    return text, total_pages, page_number


def build_single_view_text(
    *,
    warehouse: str,
    body: str,
    paged_view: PagedView | None,
    current_page: int,
    items_count: int,
    now: datetime | None = None,
) -> tuple[str, int, int]:
    timestamp = _format_timestamp(now)

    if paged_view is None:
        details = body or "Сейчас нет остатков на этом складе."
        text = (
            f"<b>🏬 Склад: {warehouse}</b>\n"
            f"{details}\n\n"
            f"<i>Всего позиций: {items_count}. Обновлено: {timestamp}</i>"
        )
        return text, 1, 1

    total_pages = paged_view.total_pages or len(paged_view.pages) or 1
    lines, page_number = _get_page_lines(paged_view, current_page)
    details = "\n".join(lines) if lines else "Нет позиций для отображения."

    text = (
        f"<b>🏬 Склад: {warehouse}</b>\n"
        "Список большой — разбил на страницы\n\n"
        f"<b>📄 Страница {page_number}/{total_pages}</b>\n"
        f"{details}\n\n"
        f"<i>Всего позиций: {items_count}. Обновлено: {timestamp}</i>"
    )

    return text, total_pages, page_number


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
    await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1)
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
            await session_storage.update_session(
                chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
            )
        else:
            message_id = await _render_card(
                bot=bot,
                chat_id=chat_id,
                text=build_stocks_menu_text(),
                inline_markup=build_stocks_menu_keyboard(),
            )
            await session_storage.update_session(
                chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
            )

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


async def _render_all_warehouses_view(
    *,
    bot: Bot,
    chat_id: int,
    items: list[WBStockItem],
    summaries: list[WarehouseSummary],
    page: int,
) -> tuple[int | None, dict[str, object]]:
    paged_view = build_pages_grouped_by_warehouse(items)
    text, total_pages, page_number = build_all_view_text(
        summaries=summaries,
        paged_view=paged_view,
        current_page=page,
    )
    total_pages = max(total_pages, 1)
    keyboard = build_stock_results_keyboard(total_pages=total_pages, current_page=page_number)
    message_id = await _render_card(
        bot=bot,
        chat_id=chat_id,
        text=text,
        inline_markup=keyboard,
    )
    mapping = _build_warehouse_mapping(summaries)
    await session_storage.update_session(
        chat_id,
        stocks_view="ALL",
        stocks_page=page_number,
        stocks_wh_map=mapping,
    )
    metadata: dict[str, object] = {
        "view": "ALL",
        "warehouse": None,
        "page": page_number,
        "total_pages": total_pages,
        "warehouses_count": len(summaries),
        "items_count": paged_view.total_items,
    }
    return message_id, metadata


async def _render_single_warehouse_view(
    *,
    bot: Bot,
    chat_id: int,
    items: list[WBStockItem],
    summaries: list[WarehouseSummary],
    warehouse_code: str,
    warehouse_name: str,
    page: int,
) -> tuple[int | None, dict[str, object]]:
    relevant_items = [
        item for item in items if item.warehouseName == warehouse_name and item.quantity > 0
    ]
    body, paged_view = format_single_warehouse(items, warehouse_name)
    mapping = _build_warehouse_mapping(summaries)
    items_count = len(relevant_items)

    if paged_view is None:
        text, total_pages, page_number = build_single_view_text(
            warehouse=warehouse_name,
            body=body,
            paged_view=None,
            current_page=1,
            items_count=items_count,
        )
        if len(text) > TELEGRAM_TEXT_LIMIT and items_count > 0:
            paged_view = build_pages_grouped_by_warehouse(relevant_items)
            text, total_pages, page_number = build_single_view_text(
                warehouse=warehouse_name,
                body="",
                paged_view=paged_view,
                current_page=page,
                items_count=items_count,
            )
    else:
        text, total_pages, page_number = build_single_view_text(
            warehouse=warehouse_name,
            body="",
            paged_view=paged_view,
            current_page=page,
            items_count=items_count,
        )

    total_pages = max(total_pages, 1)
    keyboard = build_stock_results_keyboard(total_pages=total_pages, current_page=page_number)
    message_id = await _render_card(
        bot=bot,
        chat_id=chat_id,
        text=text,
        inline_markup=keyboard,
    )
    await session_storage.update_session(
        chat_id,
        stocks_view=warehouse_code,
        stocks_page=page_number,
        stocks_wh_map=mapping,
    )
    metadata: dict[str, object] = {
        "view": "wh",
        "warehouse": warehouse_name,
        "page": page_number,
        "total_pages": total_pages,
        "warehouses_count": len(summaries),
        "items_count": items_count,
    }
    return message_id, metadata


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
            await session_storage.update_session(
                chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
            )
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
                await session_storage.update_session(
                    chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
                )
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
                    chat_id, stocks_view="summary", stocks_wh_map=mapping, stocks_page=1
                )
                logger = logger.bind(
                    warehouses_count=len(summaries), items_count=len(items), page=1, total_pages=1
                )

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Список складов показан", result="ok" if success else "fail", message_id=message_id
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


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
            await session_storage.update_session(
                chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
            )
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
                await session_storage.update_session(
                    chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
                )
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
                        chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
                    )
                else:
                    summaries = summarize_by_warehouse(items)
                    if current_view in {None, "summary"}:
                        keyboard, mapping = build_warehouses_keyboard(summaries)
                        text = build_warehouses_text(summaries, total_items=len(items))
                        await session_storage.update_session(
                            chat_id,
                            stocks_view="summary",
                            stocks_wh_map=mapping,
                            stocks_page=1,
                        )
                        message_id = await _render_card(
                            bot=bot,
                            chat_id=chat_id,
                            text=text,
                            inline_markup=keyboard,
                        )
                        logger = logger.bind(
                            warehouses_count=len(summaries),
                            items_count=len(items),
                            page=1,
                            total_pages=1,
                        )
                    elif current_view == "ALL":
                        message_id, metadata = await _render_all_warehouses_view(
                            bot=bot,
                            chat_id=chat_id,
                            items=items,
                            summaries=summaries,
                            page=1,
                        )
                        logger = logger.bind(**metadata)
                    elif current_view and current_view.startswith(WAREHOUSE_KEY_PREFIX):
                        fresh_mapping = _build_warehouse_mapping(summaries)
                        warehouse_name = fresh_mapping.get(current_view)
                        if warehouse_name is None:
                            keyboard, mapping = build_warehouses_keyboard(summaries)
                            text = build_warehouses_text(summaries, total_items=len(items))
                            await session_storage.update_session(
                                chat_id,
                                stocks_view="summary",
                                stocks_wh_map=mapping,
                                stocks_page=1,
                            )
                            message_id = await _render_card(
                                bot=bot,
                                chat_id=chat_id,
                                text=text,
                                inline_markup=keyboard,
                            )
                            logger = logger.bind(
                                warehouses_count=len(summaries),
                                items_count=len(items),
                                page=1,
                                total_pages=1,
                            )
                        else:
                            message_id, metadata = await _render_single_warehouse_view(
                                bot=bot,
                                chat_id=chat_id,
                                items=items,
                                summaries=summaries,
                                warehouse_code=current_view,
                                warehouse_name=warehouse_name,
                                page=1,
                            )
                            logger = logger.bind(**metadata)
                    else:
                        keyboard, mapping = build_warehouses_keyboard(summaries)
                        text = build_warehouses_text(summaries, total_items=len(items))
                        await session_storage.update_session(
                            chat_id,
                            stocks_view="summary",
                            stocks_wh_map=mapping,
                            stocks_page=1,
                        )
                        message_id = await _render_card(
                            bot=bot,
                            chat_id=chat_id,
                            text=text,
                            inline_markup=keyboard,
                        )
                        logger = logger.bind(
                            warehouses_count=len(summaries),
                            items_count=len(items),
                            page=1,
                            total_pages=1,
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
            await session_storage.update_session(
                chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
            )
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
                await session_storage.update_session(
                    chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
                )
            else:
                summaries = summarize_by_warehouse(items)
                if filter_value == "ALL":
                    message_id, metadata = await _render_all_warehouses_view(
                        bot=bot,
                        chat_id=chat_id,
                        items=items,
                        summaries=summaries,
                        page=1,
                    )
                    logger = logger.bind(**metadata)
                else:
                    fresh_mapping = _build_warehouse_mapping(summaries)
                    warehouse_name = fresh_mapping.get(filter_value)
                    if warehouse_name is None:
                        keyboard, mapping = build_warehouses_keyboard(summaries)
                        text = build_warehouses_text(summaries, total_items=len(items))
                        await session_storage.update_session(
                            chat_id,
                            stocks_view="summary",
                            stocks_wh_map=mapping,
                            stocks_page=1,
                        )
                        message_id = await _render_card(
                            bot=bot,
                            chat_id=chat_id,
                            text=text,
                            inline_markup=keyboard,
                        )
                        logger = logger.bind(
                            warehouses_count=len(summaries),
                            items_count=len(items),
                            page=1,
                            total_pages=1,
                        )
                    else:
                        message_id, metadata = await _render_single_warehouse_view(
                            bot=bot,
                            chat_id=chat_id,
                            items=items,
                            summaries=summaries,
                            warehouse_code=filter_value,
                            warehouse_name=warehouse_name,
                            page=1,
                        )
                        logger = logger.bind(**metadata)

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Фильтр складов обработан", result="ok" if success else "fail", message_id=message_id
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data and c.data.startswith(STOCKS_PAGE_PREFIX))
async def handle_stocks_page(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("stocks_page", request_id) as logger:
        logger.info("Переключение страницы", page_callback=callback.data)

        if callback.message is None or callback.data is None:
            await callback.answer()
            return

        await callback.answer()

        chat_id = callback.message.chat.id
        try:
            requested_page = int(callback.data[len(STOCKS_PAGE_PREFIX) :])
        except ValueError:
            requested_page = 1

        session = await session_storage.get_session(chat_id)
        current_view = session.stocks_view

        if current_view is None or current_view == "summary":
            logger.warning("Страница недоступна без выбранного представления", result="skip")
            return

        settings = get_settings()
        token_secret = settings.wb_api_token
        if token_secret is None:
            text = build_missing_token_text()
            keyboard = build_missing_token_keyboard()
            message_id = await _render_card(
                bot=bot, chat_id=chat_id, text=text, inline_markup=keyboard
            )
            await session_storage.update_session(
                chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
            )
            success = message_id is not None
            latency_ms = _calc_latency(started_at)
            structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
            logger.warning(
                "Нет токена для переключения страницы",
                result="fail" if not success else "ok",
                message_id=message_id,
            )
            structlog.contextvars.unbind_contextvars("latency_ms")
            return

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
            await session_storage.update_session(
                chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1
            )
            success = message_id is not None
            latency_ms = _calc_latency(started_at)
            structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
            logger.error(
                "Ошибка загрузки данных для смены страницы",
                result="fail" if not success else "ok",
                message_id=message_id,
            )
            structlog.contextvars.unbind_contextvars("latency_ms")
            return

        summaries = summarize_by_warehouse(items)

        if current_view == "ALL":
            message_id, metadata = await _render_all_warehouses_view(
                bot=bot,
                chat_id=chat_id,
                items=items,
                summaries=summaries,
                page=requested_page,
            )
            logger = logger.bind(**metadata)
        elif current_view.startswith(WAREHOUSE_KEY_PREFIX):
            mapping = _build_warehouse_mapping(summaries)
            warehouse_name = mapping.get(current_view)
            if warehouse_name is None:
                keyboard, mapping = build_warehouses_keyboard(summaries)
                text = build_warehouses_text(summaries, total_items=len(items))
                await session_storage.update_session(
                    chat_id,
                    stocks_view="summary",
                    stocks_wh_map=mapping,
                    stocks_page=1,
                )
                message_id = await _render_card(
                    bot=bot,
                    chat_id=chat_id,
                    text=text,
                    inline_markup=keyboard,
                )
                logger = logger.bind(
                    warehouses_count=len(summaries),
                    items_count=len(items),
                    page=1,
                    total_pages=1,
                )
            else:
                message_id, metadata = await _render_single_warehouse_view(
                    bot=bot,
                    chat_id=chat_id,
                    items=items,
                    summaries=summaries,
                    warehouse_code=current_view,
                    warehouse_name=warehouse_name,
                    page=requested_page,
                )
                logger = logger.bind(**metadata)
        else:
            keyboard, mapping = build_warehouses_keyboard(summaries)
            text = build_warehouses_text(summaries, total_items=len(items))
            await session_storage.update_session(
                chat_id,
                stocks_view="summary",
                stocks_wh_map=mapping,
                stocks_page=1,
            )
            message_id = await _render_card(
                bot=bot,
                chat_id=chat_id,
                text=text,
                inline_markup=keyboard,
            )
            logger = logger.bind(
                warehouses_count=len(summaries),
                items_count=len(items),
                page=1,
                total_pages=1,
            )

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Страница остатков переключена",
            result="ok" if success else "fail",
            message_id=message_id,
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == STOCKS_EXPORT_CALLBACK)
async def handle_stocks_export(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("stocks_export", request_id) as logger:
        logger.info("Запрошена выгрузка остатков")

        if callback.message is None:
            await callback.answer()
            return

        chat_id = callback.message.chat.id

        session = await session_storage.get_session(chat_id)
        current_view = session.stocks_view

        if current_view is None or current_view == "summary":
            logger.warning("Экспорт без выбранного представления невозможен", result="skip")
            return

        settings = get_settings()
        token_secret = settings.wb_api_token
        if token_secret is None:
            logger.warning("Нет токена для экспорта", result="fail")
            await callback.answer("Добавьте токен, чтобы выгружать остатки", show_alert=True)
            return

        token = token_secret.get_secret_value()
        try:
            items = await _load_stocks(token, force_refresh=False)
        except WBApiError as error:
            logger.error("Ошибка при выгрузке остатков", err=str(error), result="fail")
            await callback.answer("Не удалось выгрузить. Попробуйте позже", show_alert=True)
            return

        summaries = summarize_by_warehouse(items)
        mapping = session.stocks_wh_map or _build_warehouse_mapping(summaries)

        if current_view == "ALL":
            warehouse_name: str | None = None
            selected_items = [item for item in items if item.quantity > 0]
            view_label = "ALL"
            paged_view = build_pages_grouped_by_warehouse(items)
        else:
            warehouse_name = mapping.get(current_view)
            if warehouse_name is None:
                fallback = _build_warehouse_mapping(summaries)
                warehouse_name = fallback.get(current_view)
            if warehouse_name is None:
                logger.warning("Склад для экспорта не найден", result="fail")
                await callback.answer("Склад недоступен, обновите карточку", show_alert=True)
                return
            selected_items = [
                item for item in items if item.warehouseName == warehouse_name and item.quantity > 0
            ]
            view_label = current_view
            paged_view = build_pages_grouped_by_warehouse(selected_items)

        file_bytes = build_export_csv(selected_items)
        filename = build_export_filename(view_label, warehouse_name, datetime.now())
        document = BufferedInputFile(file_bytes, filename)

        await bot.send_document(chat_id=chat_id, document=document)
        await callback.answer("Файл отправлен")

        logger = logger.bind(
            view=current_view,
            warehouse=warehouse_name,
            items_count=len(selected_items),
            page=session.stocks_page,
            total_pages=max(paged_view.total_pages or len(paged_view.pages) or 1, 1),
            warehouses_count=len(summaries),
        )
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info("Файл остатков отправлен", result="ok")
        structlog.contextvars.unbind_contextvars("latency_ms")
