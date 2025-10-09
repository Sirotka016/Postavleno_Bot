from __future__ import annotations

import binascii
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from structlog.stdlib import BoundLogger

from ..core.config import get_settings
from ..core.logging import get_logger
from ..integrations.wb_client import WBApiError, WBAuthError, WBRatelimitError, WBStockItem
from ..services.export import dataframe_to_xlsx_bytes
from ..services.local import (
    LocalFileError,
    LocalJoinStats,
    build_local_only_dataframe,
    build_local_preview,
    classify_dataframe,
    dataframe_from_bytes,
    load_latest,
    perform_join,
    recompute_local_result,
    save_local_upload,
    save_result,
    save_wb_upload,
)
from ..services.stocks import (
    TELEGRAM_TEXT_LIMIT,
    PagedView,
    WarehouseSummary,
    build_export_filename,
    build_export_xlsx,
    build_pages_grouped_by_warehouse,
    format_single_warehouse,
    get_stock_data,
    summarize_by_warehouse,
)
from ..state.session import ScreenState, nav_back, nav_push, nav_replace, session_storage
from ..utils.safe_telegram import safe_delete, safe_edit, safe_send

MENU_ROUTER = Router(name="menu")

MAIN_REFRESH_CALLBACK = "main.refresh"
MAIN_EXIT_CALLBACK = "main.exit"
MAIN_STOCKS_CALLBACK = "main.stocks"
MAIN_LOCAL_CALLBACK = "main.local"

STOCKS_OPEN_CALLBACK = "stocks.open"
STOCKS_VIEW_CALLBACK = "stocks.view"
STOCKS_REFRESH_CALLBACK = "stocks.refresh"
STOCKS_BACK_CALLBACK = "stocks.back"
STOCKS_EXPORT_CALLBACK = "stocks.export"
STOCKS_FILTER_PREFIX = "stocks.filter:"
STOCKS_FILTER_ALL = f"{STOCKS_FILTER_PREFIX}ALL"
STOCKS_PAGE_PREFIX = "stocks.page:"
WAREHOUSE_KEY_PREFIX = "wh:"

LOCAL_OPEN_CALLBACK = "local.open"
LOCAL_REFRESH_CALLBACK = "local.refresh"
LOCAL_BACK_CALLBACK = "local.back"
LOCAL_EXPORT_CALLBACK = "local.export"
LOCAL_UPLOAD_CALLBACK = "local.upload"

SCREEN_MAIN = "MAIN"
SCREEN_WB_OPEN = "WB_OPEN"
SCREEN_WB_LIST = "WB_LIST"
SCREEN_WB_ALL = "WB_ALL"
SCREEN_WB_WH = "WB_WH"
SCREEN_WB_PAGE = "WB_PAGE"
SCREEN_LOCAL_OPEN = "LOCAL_OPEN"
SCREEN_LOCAL_UPLOAD = "LOCAL_UPLOAD"
SCREEN_LOCAL_VIEW = "LOCAL_VIEW"


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
        "Нажмите «🏭 Остатки Склад», чтобы сверить свои остатки со складами WB.\n\n"
        "Используйте кнопки под сообщением, чтобы обновить карточку или выйти.\n\n"
        f"<i>Обновлено: {timestamp}</i>"
    )


def build_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📦 Остатки WB", callback_data=MAIN_STOCKS_CALLBACK),
                InlineKeyboardButton(text="🏭 Остатки Склад", callback_data=MAIN_LOCAL_CALLBACK),
            ],
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


def build_local_menu_text() -> str:
    return (
        "<b>🏭 Остатки нашего склада</b>\n\n"
        "Здесь вы можете загрузить актуальные остатки своего склада, "
        "а также сверить их с позициями Wildberries.\n\n"
        "Нажмите «📤 Загрузить Остатки», чтобы добавить файлы."
    )


def build_local_menu_keyboard(*, has_export: bool) -> InlineKeyboardMarkup:
    inline_keyboard: list[list[InlineKeyboardButton]] = []
    if has_export:
        inline_keyboard.append(
            [InlineKeyboardButton(text="⬇️ Выгрузить", callback_data=LOCAL_EXPORT_CALLBACK)]
        )

    inline_keyboard.append(
        [InlineKeyboardButton(text="📤 Загрузить Остатки", callback_data=LOCAL_UPLOAD_CALLBACK)]
    )

    inline_keyboard.append(
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=LOCAL_REFRESH_CALLBACK),
            InlineKeyboardButton(text="⬅️ Назад", callback_data=LOCAL_BACK_CALLBACK),
        ]
    )
    inline_keyboard.append(
        [InlineKeyboardButton(text="🚪 Выйти", callback_data=MAIN_EXIT_CALLBACK)]
    )
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def _checkbox(value: bool) -> str:
    return "✅" if value else "⬜"


def _format_local_summary(stats: LocalJoinStats) -> str:
    return (
        "✅ Оба файла загружены. Данные сопоставлены.\n"
        f"• Позиции WB: {stats.wb_count}\n"
        f"• Найдено совпадений по артикулу: {stats.matched}\n"
        f"• Отброшено позиций вне WB: {stats.dropped}"
    )


def build_local_upload_text(
    *,
    wb_uploaded: bool,
    local_uploaded: bool,
    stats: LocalJoinStats | None = None,
    message: str | None = None,
) -> str:
    lines = [
        "<b>📤 Загрузка остатков</b>",
        "",
        f"{_checkbox(wb_uploaded)} Загрузите EXCEL файл с остатками на ВСЕХ складах WB",
        f"{_checkbox(local_uploaded)} Загрузите EXCEL файл с остатками на Складе",
        "",
        "После загрузки обоих файлов я сопоставлю номенклатуру и подготовлю итог.",
    ]

    if stats:
        lines.append("")
        lines.append(_format_local_summary(stats))

    if message:
        lines.append("")
        lines.append(message)

    return "\n".join(lines)


def build_local_upload_keyboard(*, ready: bool) -> InlineKeyboardMarkup:
    inline_keyboard: list[list[InlineKeyboardButton]] = []
    if ready:
        inline_keyboard.append(
            [InlineKeyboardButton(text="⬇️ Выгрузить", callback_data=LOCAL_EXPORT_CALLBACK)]
        )

    inline_keyboard.append(
        [InlineKeyboardButton(text="📤 Загрузить Остатки", callback_data=LOCAL_UPLOAD_CALLBACK)]
    )
    inline_keyboard.append(
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=LOCAL_REFRESH_CALLBACK),
            InlineKeyboardButton(text="⬅️ Назад", callback_data=LOCAL_BACK_CALLBACK),
        ]
    )
    inline_keyboard.append(
        [InlineKeyboardButton(text="🚪 Выйти", callback_data=MAIN_EXIT_CALLBACK)]
    )
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def build_local_export_text(preview_lines: list[str], total: int) -> str:
    body = "\n".join(preview_lines)
    return "<b>🏭 Остатки склада (итог)</b>\n" f"{body}\n" f"<i>Показаны первые 25 из {total}</i>"


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


def _calc_latency(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _bind_screen(logger: BoundLogger, screen: str) -> BoundLogger:
    return logger.bind(screen=screen)


async def _ensure_session(chat_id: int) -> Any:
    return await session_storage.get_session(chat_id)


async def _load_stocks(token: str, *, force_refresh: bool) -> list[WBStockItem]:
    return await get_stock_data(token, force_refresh=force_refresh)


def _build_error_response(error: Exception) -> tuple[str, InlineKeyboardMarkup]:
    if isinstance(error, WBAuthError):
        return build_auth_error_text(), build_error_keyboard()
    if isinstance(error, WBRatelimitError):
        return build_rate_limit_text(error.retry_after), build_error_keyboard()
    text = (
        "<b>📦 Остатки на складах WB</b>\n\n"
        "Не удалось получить остатки. Попробуйте обновить карточку позже."
    )
    return text, build_error_keyboard()


async def _render_main_menu(bot: Bot, chat_id: int) -> int | None:
    session = await _ensure_session(chat_id)
    session.history.clear()
    nav_replace(session, ScreenState(name=SCREEN_MAIN, params={}))
    await session_storage.update_session(
        chat_id,
        stocks_view=None,
        stocks_wh_map={},
        stocks_page=1,
        local_page=1,
    )
    return await _render_card(
        bot=bot,
        chat_id=chat_id,
        text=build_greeting_text(),
        inline_markup=build_main_keyboard(),
    )


async def _render_stocks_entry(
    bot: Bot,
    chat_id: int,
    *,
    nav_action: str,
) -> int | None:
    session = await _ensure_session(chat_id)
    state = ScreenState(name=SCREEN_WB_OPEN, params={})
    if nav_action == "push":
        nav_push(session, state)
    else:
        nav_replace(session, state)
    await session_storage.update_session(chat_id, stocks_view=None, stocks_wh_map={}, stocks_page=1)

    settings = get_settings()
    token_secret = settings.wb_api_token
    if token_secret is None:
        return await _render_card(
            bot=bot,
            chat_id=chat_id,
            text=build_missing_token_text(),
            inline_markup=build_missing_token_keyboard(),
        )
    return await _render_card(
        bot=bot,
        chat_id=chat_id,
        text=build_stocks_menu_text(),
        inline_markup=build_stocks_menu_keyboard(),
    )


async def _render_warehouses_list(
    bot: Bot,
    chat_id: int,
    *,
    nav_action: str,
    force_refresh: bool,
) -> tuple[int | None, dict[str, Any]]:
    session = await _ensure_session(chat_id)
    settings = get_settings()
    token_secret = settings.wb_api_token
    if token_secret is None:
        nav_replace(session, ScreenState(name=SCREEN_WB_OPEN, params={}))
        message_id = await _render_card(
            bot=bot,
            chat_id=chat_id,
            text=build_missing_token_text(),
            inline_markup=build_missing_token_keyboard(),
        )
        return message_id, {"result": "missing_token"}

    token = token_secret.get_secret_value()
    try:
        items = await _load_stocks(token, force_refresh=force_refresh)
    except WBApiError as error:
        text, keyboard = _build_error_response(error)
        nav_replace(session, ScreenState(name=SCREEN_WB_OPEN, params={}))
        message_id = await _render_card(
            bot=bot,
            chat_id=chat_id,
            text=text,
            inline_markup=keyboard,
        )
        return message_id, {"result": "error"}

    summaries = summarize_by_warehouse(items)
    keyboard, mapping = build_warehouses_keyboard(summaries)
    text = build_warehouses_text(summaries, total_items=len(items))

    state = ScreenState(name=SCREEN_WB_LIST, params={})
    if nav_action == "push":
        nav_push(session, state)
    else:
        nav_replace(session, state)
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
    return message_id, {
        "result": "ok",
        "warehouses_count": len(summaries),
        "items_count": len(items),
        "page": 1,
        "total_pages": 1,
    }


async def _render_all_view(
    bot: Bot,
    chat_id: int,
    *,
    items: list[WBStockItem],
    summaries: list[WarehouseSummary],
    requested_page: int,
    nav_action: str,
    screen_state: ScreenState,
) -> tuple[int | None, dict[str, Any]]:
    session = await _ensure_session(chat_id)
    paged_view = build_pages_grouped_by_warehouse(items)
    text, total_pages, page_number = build_all_view_text(
        summaries=summaries,
        paged_view=paged_view,
        current_page=requested_page,
    )
    total_pages = max(total_pages, 1)
    keyboard = build_stock_results_keyboard(total_pages=total_pages, current_page=page_number)

    if nav_action == "push":
        nav_push(session, screen_state)
    else:
        nav_replace(session, screen_state)
    nav_replace(
        session,
        ScreenState(
            name=screen_state.name,
            params={"page": page_number, "view": "ALL"},
        ),
    )

    await session_storage.update_session(
        chat_id,
        stocks_view="ALL",
        stocks_page=page_number,
        stocks_wh_map=_build_warehouse_mapping(summaries),
    )

    message_id = await _render_card(
        bot=bot,
        chat_id=chat_id,
        text=text,
        inline_markup=keyboard,
    )
    return message_id, {
        "view": "ALL",
        "warehouse": None,
        "page": page_number,
        "total_pages": total_pages,
        "warehouses_count": len(summaries),
        "items_count": paged_view.total_items,
    }


async def _render_single_view(
    bot: Bot,
    chat_id: int,
    *,
    items: list[WBStockItem],
    summaries: list[WarehouseSummary],
    warehouse_code: str,
    warehouse_name: str,
    requested_page: int,
    nav_action: str,
    screen_state: ScreenState,
) -> tuple[int | None, dict[str, Any]]:
    session = await _ensure_session(chat_id)
    relevant_items = [
        item for item in items if item.warehouseName == warehouse_name and item.quantity > 0
    ]
    body, paged_view = format_single_warehouse(items, warehouse_name)
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
                current_page=requested_page,
                items_count=items_count,
            )
    else:
        text, total_pages, page_number = build_single_view_text(
            warehouse=warehouse_name,
            body="",
            paged_view=paged_view,
            current_page=requested_page,
            items_count=items_count,
        )

    total_pages = max(total_pages, 1)
    keyboard = build_stock_results_keyboard(total_pages=total_pages, current_page=page_number)

    if nav_action == "push":
        nav_push(session, screen_state)
    else:
        nav_replace(session, screen_state)
    nav_replace(
        session,
        ScreenState(
            name=screen_state.name,
            params={"wh": warehouse_code, "page": page_number, "view": warehouse_code},
        ),
    )

    await session_storage.update_session(
        chat_id,
        stocks_view=warehouse_code,
        stocks_page=page_number,
        stocks_wh_map=_build_warehouse_mapping(summaries),
    )

    message_id = await _render_card(
        bot=bot,
        chat_id=chat_id,
        text=text,
        inline_markup=keyboard,
    )
    return message_id, {
        "view": "wh",
        "warehouse": warehouse_name,
        "page": page_number,
        "total_pages": total_pages,
        "warehouses_count": len(summaries),
        "items_count": items_count,
    }


def _local_status(session) -> dict[str, bool]:
    return {
        "wb": session.local_uploaded_wb is not None,
        "local": session.local_uploaded_local is not None,
        "ready": session.local_join_ready,
    }


async def _render_local_home(
    bot: Bot,
    chat_id: int,
    *,
    nav_action: str,
) -> int | None:
    session = await _ensure_session(chat_id)
    status = _local_status(session)
    has_export = status["ready"] or status["local"]
    state = ScreenState(name=SCREEN_LOCAL_OPEN, params={})
    if nav_action == "push":
        nav_push(session, state)
    else:
        nav_replace(session, state)
    return await _render_card(
        bot=bot,
        chat_id=chat_id,
        text=build_local_menu_text(),
        inline_markup=build_local_menu_keyboard(has_export=has_export),
    )


async def _render_local_upload(
    bot: Bot,
    chat_id: int,
    *,
    nav_action: str,
    stats: LocalJoinStats | None = None,
    message: str | None = None,
) -> int | None:
    session = await _ensure_session(chat_id)
    status = _local_status(session)
    state = ScreenState(
        name=SCREEN_LOCAL_UPLOAD,
        params={"wb": status["wb"], "local": status["local"], "ready": status["ready"]},
    )
    if nav_action == "push":
        nav_push(session, state)
    else:
        nav_replace(session, state)
    text = build_local_upload_text(
        wb_uploaded=status["wb"],
        local_uploaded=status["local"],
        stats=stats if status["ready"] else None,
        message=message,
    )
    keyboard = build_local_upload_keyboard(ready=status["ready"])
    return await _render_card(
        bot=bot,
        chat_id=chat_id,
        text=text,
        inline_markup=keyboard,
    )


async def _render_local_preview(
    bot: Bot,
    chat_id: int,
    dataframe,
    *,
    nav_action: str,
) -> int | None:
    session = await _ensure_session(chat_id)
    state = ScreenState(name=SCREEN_LOCAL_VIEW, params={})
    if nav_action == "push":
        nav_push(session, state)
    else:
        nav_replace(session, state)

    lines, total = build_local_preview(dataframe)
    text = build_local_export_text(lines, total)
    keyboard = build_local_menu_keyboard(has_export=True)
    return await _render_card(
        bot=bot,
        chat_id=chat_id,
        text=text,
        inline_markup=keyboard,
    )


async def _render_state(
    bot: Bot,
    chat_id: int,
    state: ScreenState,
) -> int | None:
    session = await _ensure_session(chat_id)
    if state.name == SCREEN_MAIN:
        return await _render_main_menu(bot, chat_id)
    if state.name == SCREEN_WB_OPEN:
        return await _render_stocks_entry(bot, chat_id, nav_action="replace")
    if state.name == SCREEN_WB_LIST:
        message_id, _ = await _render_warehouses_list(
            bot,
            chat_id,
            nav_action="replace",
            force_refresh=False,
        )
        return message_id
    if state.name in {SCREEN_WB_ALL, SCREEN_WB_PAGE}:
        view = state.params.get("view", "ALL")
        page = int(state.params.get("page", session.stocks_page))
        settings = get_settings()
        token_secret = settings.wb_api_token
        if token_secret is None:
            return await _render_stocks_entry(bot, chat_id, nav_action="replace")
        token = token_secret.get_secret_value()
        try:
            items = await _load_stocks(token, force_refresh=False)
        except WBApiError:
            return await _render_stocks_entry(bot, chat_id, nav_action="replace")
        summaries = summarize_by_warehouse(items)
        if view == "ALL":
            message_id, _ = await _render_all_view(
                bot,
                chat_id,
                items=items,
                summaries=summaries,
                requested_page=page,
                nav_action="replace",
                screen_state=ScreenState(name=SCREEN_WB_ALL, params={"page": page}),
            )
            return message_id
        warehouse_code = state.params.get("wh") or state.params.get("view")
        warehouse_name = _build_warehouse_mapping(summaries).get(warehouse_code or "")
        if not warehouse_name:
            message_id, _ = await _render_warehouses_list(
                bot,
                chat_id,
                nav_action="replace",
                force_refresh=False,
            )
            return message_id
        message_id, _ = await _render_single_view(
            bot,
            chat_id,
            items=items,
            summaries=summaries,
            warehouse_code=warehouse_code or "",
            warehouse_name=warehouse_name,
            requested_page=page,
            nav_action="replace",
            screen_state=ScreenState(
                name=SCREEN_WB_WH, params={"wh": warehouse_code or "", "page": page}
            ),
        )
        return message_id
    if state.name == SCREEN_WB_WH:
        warehouse_code = state.params.get("wh")
        page = int(state.params.get("page", 1))
        settings = get_settings()
        token_secret = settings.wb_api_token
        if token_secret is None:
            return await _render_stocks_entry(bot, chat_id, nav_action="replace")
        token = token_secret.get_secret_value()
        try:
            items = await _load_stocks(token, force_refresh=False)
        except WBApiError:
            return await _render_stocks_entry(bot, chat_id, nav_action="replace")
        summaries = summarize_by_warehouse(items)
        warehouse_name = _build_warehouse_mapping(summaries).get(warehouse_code or "")
        if not warehouse_name:
            message_id, _ = await _render_warehouses_list(
                bot,
                chat_id,
                nav_action="replace",
                force_refresh=False,
            )
            return message_id
        message_id, _ = await _render_single_view(
            bot,
            chat_id,
            items=items,
            summaries=summaries,
            warehouse_code=warehouse_code or "",
            warehouse_name=warehouse_name,
            requested_page=page,
            nav_action="replace",
            screen_state=ScreenState(
                name=SCREEN_WB_WH, params={"wh": warehouse_code or "", "page": page}
            ),
        )
        return message_id
    if state.name == SCREEN_LOCAL_OPEN:
        return await _render_local_home(bot, chat_id, nav_action="replace")
    if state.name == SCREEN_LOCAL_UPLOAD:
        return await _render_local_upload(bot, chat_id, nav_action="replace")
    if state.name == SCREEN_LOCAL_VIEW:
        result_df = load_latest(chat_id, "result")
        if result_df is None:
            return await _render_local_home(bot, chat_id, nav_action="replace")
        return await _render_local_preview(bot, chat_id, result_df, nav_action="replace")
    return await _render_main_menu(bot, chat_id)


async def _handle_stocks_display(
    *,
    bot: Bot,
    chat_id: int,
    view: str,
    warehouse_code: str | None,
    page: int,
    nav_action: str,
) -> tuple[int | None, dict[str, Any]]:
    settings = get_settings()
    token_secret = settings.wb_api_token
    if token_secret is None:
        message_id = await _render_stocks_entry(bot, chat_id, nav_action="replace")
        return message_id, {"result": "missing_token"}

    token = token_secret.get_secret_value()
    try:
        items = await _load_stocks(token, force_refresh=False)
    except WBApiError as error:
        text, keyboard = _build_error_response(error)
        session = await _ensure_session(chat_id)
        nav_replace(session, ScreenState(name=SCREEN_WB_OPEN, params={}))
        message_id = await _render_card(
            bot=bot,
            chat_id=chat_id,
            text=text,
            inline_markup=keyboard,
        )
        return message_id, {"result": "error"}

    summaries = summarize_by_warehouse(items)
    if view == "ALL":
        return await _render_all_view(
            bot,
            chat_id,
            items=items,
            summaries=summaries,
            requested_page=page,
            nav_action=nav_action,
            screen_state=ScreenState(name=SCREEN_WB_ALL, params={"page": page}),
        )

    mapping = _build_warehouse_mapping(summaries)
    warehouse_name = mapping.get(warehouse_code or "")
    if warehouse_name is None:
        return await _render_warehouses_list(
            bot,
            chat_id,
            nav_action="replace",
            force_refresh=False,
        )
    return await _render_single_view(
        bot,
        chat_id,
        items=items,
        summaries=summaries,
        warehouse_code=warehouse_code or "",
        warehouse_name=warehouse_name,
        requested_page=page,
        nav_action=nav_action,
        screen_state=ScreenState(
            name=SCREEN_WB_WH, params={"wh": warehouse_code or "", "page": page}
        ),
    )


@MENU_ROUTER.message(Command("start"))
async def handle_start(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    with _action_logger("start", request_id) as logger:
        logger = _bind_screen(logger, SCREEN_MAIN)
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
        logger = _bind_screen(logger, SCREEN_MAIN)
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
        logger = _bind_screen(logger, SCREEN_MAIN)
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
        logger = _bind_screen(logger, SCREEN_WB_OPEN)
        logger.info("Переход в раздел остатков")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()

        message_id = await _render_stocks_entry(bot, callback.message.chat.id, nav_action="push")

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Раздел остатков открыт", result="ok" if success else "fail", message_id=message_id
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == STOCKS_VIEW_CALLBACK)
async def handle_stocks_view(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("stocks_view", request_id) as logger:
        logger = _bind_screen(logger, SCREEN_WB_LIST)
        logger.info("Запрошен список складов")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        chat_id = callback.message.chat.id

        message_id, metadata = await _render_warehouses_list(
            bot,
            chat_id,
            nav_action="push",
            force_refresh=False,
        )

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Список складов показан",
            result="ok" if success else "fail",
            message_id=message_id,
            **metadata,
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
        session = await _ensure_session(chat_id)
        current_state = (
            session.history[-1] if session.history else ScreenState(name=SCREEN_MAIN, params={})
        )

        if current_state.name == SCREEN_WB_LIST:
            message_id, metadata = await _render_warehouses_list(
                bot,
                chat_id,
                nav_action="replace",
                force_refresh=True,
            )
            screen = SCREEN_WB_LIST
        elif current_state.name in {SCREEN_WB_ALL, SCREEN_WB_WH, SCREEN_WB_PAGE}:
            view = current_state.params.get("view") or (
                current_state.params.get("wh") if current_state.name == SCREEN_WB_WH else "ALL"
            )
            page = int(current_state.params.get("page", session.stocks_page))
            warehouse_code = view if view and view.startswith(WAREHOUSE_KEY_PREFIX) else None
            message_id, metadata = await _handle_stocks_display(
                bot=bot,
                chat_id=chat_id,
                view="ALL" if warehouse_code is None else "wh",
                warehouse_code=warehouse_code,
                page=page,
                nav_action="replace",
            )
            screen = metadata.get("view", SCREEN_WB_ALL)
        else:
            message_id = await _render_stocks_entry(bot, chat_id, nav_action="replace")
            metadata = {"result": "menu"}
            screen = SCREEN_WB_OPEN

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger = _bind_screen(logger, screen)
        logger.info(
            "Раздел остатков обновлён",
            result="ok" if success else "fail",
            message_id=message_id,
            **metadata,
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == STOCKS_BACK_CALLBACK)
async def handle_stocks_back(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("stocks_back", request_id) as logger:
        logger.info("Возврат на предыдущий экран")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        chat_id = callback.message.chat.id
        session = await _ensure_session(chat_id)
        previous = nav_back(session)
        if previous is None:
            message_id = await _render_main_menu(bot, chat_id)
            screen = SCREEN_MAIN
        else:
            message_id = await _render_state(bot, chat_id, previous)
            screen = previous.name

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger = _bind_screen(logger, screen)
        logger.info("Возврат выполнен", result="ok" if success else "fail", message_id=message_id)
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

        if filter_value == "ALL":
            view = "ALL"
            warehouse_code: str | None = None
        else:
            view = "wh"
            warehouse_code = filter_value

        message_id, metadata = await _handle_stocks_display(
            bot=bot,
            chat_id=chat_id,
            view=view,
            warehouse_code=warehouse_code,
            page=1,
            nav_action="push",
        )

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        screen = SCREEN_WB_ALL if view == "ALL" else SCREEN_WB_WH
        logger = _bind_screen(logger, screen)
        logger.info(
            "Фильтр складов обработан",
            result="ok" if success else "fail",
            message_id=message_id,
            **metadata,
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

        session = await _ensure_session(chat_id)
        current_view = session.stocks_view

        if current_view is None or current_view == "summary":
            logger.warning("Страница недоступна без выбранного представления", result="skip")
            return

        view_type = "ALL" if current_view == "ALL" else "wh"
        warehouse_code = current_view if view_type == "wh" else None

        message_id, metadata = await _handle_stocks_display(
            bot=bot,
            chat_id=chat_id,
            view=view_type,
            warehouse_code=warehouse_code,
            page=requested_page,
            nav_action="push",
        )

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger = _bind_screen(logger, SCREEN_WB_PAGE)
        logger.info(
            "Страница остатков переключена",
            result="ok" if success else "fail",
            message_id=message_id,
            **metadata,
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
        session = await _ensure_session(chat_id)
        current_view = session.stocks_view

        if current_view is None or current_view == "summary":
            logger.warning("Экспорт без выбранного представления невозможен", result="skip")
            await callback.answer("Выберите представление перед экспортом", show_alert=True)
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
            selected_items = [item for item in items if item.quantity > 0]
            warehouse_name: str | None = None
            view_label = "ALL"
            paged_view = build_pages_grouped_by_warehouse(items)
        else:
            warehouse_name = mapping.get(current_view)
            if warehouse_name is None:
                warehouse_name = _build_warehouse_mapping(summaries).get(current_view)
            if warehouse_name is None:
                logger.warning("Склад для экспорта не найден", result="fail")
                await callback.answer("Склад недоступен, обновите карточку", show_alert=True)
                return
            selected_items = [
                item for item in items if item.warehouseName == warehouse_name and item.quantity > 0
            ]
            view_label = current_view
            paged_view = build_pages_grouped_by_warehouse(selected_items)

        file_bytes = build_export_xlsx(selected_items)
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


@MENU_ROUTER.callback_query(lambda c: c.data == MAIN_LOCAL_CALLBACK)
async def handle_local_entry(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("local_open", request_id) as logger:
        logger = _bind_screen(logger, SCREEN_LOCAL_OPEN)
        logger.info("Переход в раздел локальных остатков")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        message_id = await _render_local_home(bot, callback.message.chat.id, nav_action="push")
        success = message_id is not None

        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Раздел локальных остатков открыт",
            result="ok" if success else "fail",
            message_id=message_id,
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == LOCAL_OPEN_CALLBACK)
async def handle_local_open(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("local_home", request_id) as logger:
        logger = _bind_screen(logger, SCREEN_LOCAL_OPEN)
        logger.info("Возвращение на экран локальных остатков")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        message_id = await _render_local_home(bot, callback.message.chat.id, nav_action="replace")
        success = message_id is not None

        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Экран локальных остатков", result="ok" if success else "fail", message_id=message_id
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == LOCAL_REFRESH_CALLBACK)
async def handle_local_refresh(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("local_refresh", request_id) as logger:
        logger.info("Запрошено обновление локальных остатков")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        chat_id = callback.message.chat.id
        session = await _ensure_session(chat_id)
        current_state = (
            session.history[-1]
            if session.history
            else ScreenState(name=SCREEN_LOCAL_OPEN, params={})
        )

        if session.local_join_ready:
            result = recompute_local_result(chat_id)
            if result:
                result_df, stats = result
                await _render_local_preview(bot, chat_id, result_df, nav_action="replace")
                message_id = await _render_local_upload(
                    bot,
                    chat_id,
                    nav_action="replace",
                    stats=stats,
                )
                screen = SCREEN_LOCAL_UPLOAD
                metadata = {"result": "refreshed", "items": len(result_df)}
            else:
                message_id = await _render_local_upload(
                    bot,
                    chat_id,
                    nav_action="replace",
                    message="Нет данных для обновления",
                )
                screen = SCREEN_LOCAL_UPLOAD
                metadata = {"result": "missing"}
        elif current_state.name == SCREEN_LOCAL_UPLOAD:
            message_id = await _render_local_upload(bot, chat_id, nav_action="replace")
            screen = SCREEN_LOCAL_UPLOAD
            metadata = {"result": "upload"}
        else:
            message_id = await _render_local_home(bot, chat_id, nav_action="replace")
            screen = SCREEN_LOCAL_OPEN
            metadata = {"result": "home"}

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger = _bind_screen(logger, screen)
        logger.info(
            "Локальные остатки обновлены",
            result="ok" if success else "fail",
            message_id=message_id,
            **metadata,
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == LOCAL_BACK_CALLBACK)
async def handle_local_back(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("local_back", request_id) as logger:
        logger.info("Возврат по истории локальных остатков")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        chat_id = callback.message.chat.id
        session = await _ensure_session(chat_id)
        previous = nav_back(session)
        if previous is None:
            message_id = await _render_main_menu(bot, chat_id)
            screen = SCREEN_MAIN
        else:
            message_id = await _render_state(bot, chat_id, previous)
            screen = previous.name

        success = message_id is not None
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger = _bind_screen(logger, screen)
        logger.info(
            "Возврат по локальным остаткам",
            result="ok" if success else "fail",
            message_id=message_id,
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == LOCAL_UPLOAD_CALLBACK)
async def handle_local_upload_button(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("local_upload_screen", request_id) as logger:
        logger = _bind_screen(logger, SCREEN_LOCAL_UPLOAD)
        logger.info("Переход на экран загрузки локальных остатков")

        if callback.message is None:
            await callback.answer()
            return

        await callback.answer()
        message_id = await _render_local_upload(bot, callback.message.chat.id, nav_action="push")
        success = message_id is not None

        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger.info(
            "Экран загрузки локальных остатков",
            result="ok" if success else "fail",
            message_id=message_id,
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.callback_query(lambda c: c.data == LOCAL_EXPORT_CALLBACK)
async def handle_local_export(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("local_export", request_id) as logger:
        logger.info("Запрошена выгрузка локальных остатков")

        if callback.message is None:
            await callback.answer()
            return

        chat_id = callback.message.chat.id
        session = await _ensure_session(chat_id)

        result_path = Path(f"data/local/{chat_id}/result.xlsx")
        if session.local_join_ready and result_path.exists():
            file = FSInputFile(result_path)
            await bot.send_document(chat_id=chat_id, document=file)
            dataframe = load_latest(chat_id, "result")
            if dataframe is not None:
                await _render_local_preview(bot, chat_id, dataframe, nav_action="replace")
            await callback.answer("Файл отправлен")
            total = len(dataframe) if dataframe is not None else 0
            metadata = {"result": "sent", "items": total}
        else:
            dataframe = build_local_only_dataframe(chat_id)
            if dataframe is None or dataframe.empty:
                await callback.answer("Нет данных для выгрузки", show_alert=True)
                metadata = {"result": "empty"}
            else:
                bytes_data = dataframe_to_xlsx_bytes(dataframe)
                filename = f"local_stock_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                await bot.send_document(
                    chat_id=chat_id, document=BufferedInputFile(bytes_data, filename)
                )
                lines, total = build_local_preview(
                    dataframe.rename(columns={"Количество": "Количество_склад"})
                )
                text = build_local_export_text(lines, total)
                await _render_card(
                    bot=bot,
                    chat_id=chat_id,
                    text=text,
                    inline_markup=build_local_menu_keyboard(has_export=True),
                )
                await callback.answer("Файл отправлен")
                metadata = {"result": "local_only", "items": total}

        success = metadata.get("result") != "empty"
        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger = _bind_screen(logger, SCREEN_LOCAL_VIEW)
        logger.info(
            "Локальные остатки выгружены",
            result="ok" if success else "fail",
            message_id=None,
            **metadata,
        )
        structlog.contextvars.unbind_contextvars("latency_ms")


@MENU_ROUTER.message(F.document)
async def handle_local_document(
    message: Message, bot: Bot, request_id: str, started_at: float
) -> None:
    with _action_logger("local_document", request_id) as logger:
        chat_id = message.chat.id
        session = await _ensure_session(chat_id)
        if not session.history or session.history[-1].name != SCREEN_LOCAL_UPLOAD:
            logger.warning("Документ получен вне экрана загрузки", result="skip")
            await safe_delete(bot, chat_id=chat_id, message_id=message.message_id)
            return

        document = message.document
        if document is None:
            await safe_delete(bot, chat_id=chat_id, message_id=message.message_id)
            return

        await safe_delete(bot, chat_id=chat_id, message_id=message.message_id)

        try:
            file_data = await bot.download(document)
        except Exception as error:  # pragma: no cover - best effort
            logger.error("Не удалось скачать документ", err=str(error), result="fail")
            await _render_local_upload(
                bot,
                chat_id,
                nav_action="replace",
                message="Не удалось скачать файл. Попробуйте ещё раз.",
            )
            return

        assert file_data is not None
        content = file_data.read()
        file_name = document.file_name or "uploaded.xlsx"

        try:
            dataframe = dataframe_from_bytes(content, file_name)
        except LocalFileError as error:
            logger.warning("Файл не распознан", err=str(error), result="fail")
            await _render_local_upload(
                bot,
                chat_id,
                nav_action="replace",
                message=str(error),
            )
            return

        classification = classify_dataframe(dataframe)
        stats: LocalJoinStats | None = None
        message_text: str | None = None

        if classification == "WB":
            save_wb_upload(chat_id, dataframe)
            session.local_uploaded_wb = Path(f"data/local/{chat_id}/wb.xlsx")
            logger.info("Загружен файл WB", result="ok")
        elif classification == "LOCAL":
            save_local_upload(chat_id, dataframe)
            session.local_uploaded_local = Path(f"data/local/{chat_id}/local.xlsx")
            logger.info("Загружен локальный файл", result="ok")
        else:
            message_text = (
                "Не узнаю формат. Нужны столбцы supplierArticle/nmId/warehouseName/quantity для WB"
                " и Артикул/Количество для склада."
            )
            logger.warning("Файл не классифицирован", result="fail")

        status = _local_status(session)
        if status["wb"] and status["local"]:
            wb_df = load_latest(chat_id, "wb")
            local_df = load_latest(chat_id, "local")
            if wb_df is not None and local_df is not None:
                result_df, stats = perform_join(wb_df, local_df)
                save_result(chat_id, result_df)
                session.local_join_ready = True
                session.local_page = 1
                logger.info(
                    "Данные сопоставлены",
                    result="ok",
                    matched=stats.matched,
                    dropped=stats.dropped,
                )
            else:
                message_text = "Не удалось прочитать загруженные данные. Попробуйте ещё раз."
                logger.warning("Не удалось сопоставить", result="fail")
        else:
            session.local_join_ready = False

        await _render_local_upload(
            bot,
            chat_id,
            nav_action="replace",
            stats=stats,
            message=message_text,
        )

        latency_ms = _calc_latency(started_at)
        structlog.contextvars.bind_contextvars(latency_ms=latency_ms)
        logger = _bind_screen(logger, SCREEN_LOCAL_UPLOAD)
        logger.info("Документ обработан", result="ok")
        structlog.contextvars.unbind_contextvars("latency_ms")
