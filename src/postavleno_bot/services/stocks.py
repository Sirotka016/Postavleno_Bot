from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pandas as pd
import structlog

from ..integrations.wb_client import WBStockItem, fetch_stocks_all
from .export import dataframe_to_xlsx_bytes

_CACHE_TTL = timedelta(seconds=45)
_RATE_LIMIT_WINDOW = timedelta(minutes=1)
_INITIAL_DATE_FROM = datetime(2019, 6, 20, tzinfo=UTC)


@dataclass(slots=True)
class _CacheEntry:
    items: list[WBStockItem]
    fetched_at: datetime
    expires_at: datetime


@dataclass(slots=True)
class WarehouseSummary:
    name: str
    total_qty: int
    sku_count: int


@dataclass(slots=True)
class Page:
    number: int
    lines: list[str]


@dataclass(slots=True)
class PagedView:
    pages: list[Page]
    total_items: int
    total_pages: int


LINES_PER_PAGE = 25
TELEGRAM_TEXT_LIMIT = 4096

EXPORT_HEADERS = [
    "Склад",
    "Артикул",
    "nmId",
    "Штрихкод",
    "Кол-во",
    "Категория",
    "Предмет",
    "Бренд",
    "Размер",
    "Цена",
    "Скидка",
]


_cache: dict[str, _CacheEntry] = {}
_logger = structlog.get_logger(__name__)


async def get_stock_data(token: str, *, force_refresh: bool = False) -> list[WBStockItem]:
    """Кэширует результаты. При force_refresh игнорирует TTL, но уважает rate-limit."""

    now = datetime.now(UTC)
    entry = _cache.get(token)

    if entry and entry.expires_at > now and not force_refresh:
        _logger.debug("Stocks cache hit", result="hit")
        return entry.items

    if entry and force_refresh and now - entry.fetched_at < _RATE_LIMIT_WINDOW:
        _logger.warning("Stocks refresh throttled", result="throttled")
        return entry.items

    items = await fetch_stocks_all(token, date_from=_INITIAL_DATE_FROM)
    expires_at = now + _CACHE_TTL
    _cache[token] = _CacheEntry(items=items, fetched_at=now, expires_at=expires_at)
    _logger.info("Stocks cache populated", items_count=len(items), result="ok")
    return items


def summarize_by_warehouse(items: list[WBStockItem]) -> list[WarehouseSummary]:
    groups: dict[str, tuple[int, set[int]]] = defaultdict(lambda: (0, set()))

    for item in items:
        total, sku_set = groups[item.warehouseName]
        total += item.quantity
        sku_set.add(item.nmId)
        groups[item.warehouseName] = (total, sku_set)

    summaries: list[WarehouseSummary] = []
    for name, (total, sku_set) in groups.items():
        if total <= 0:
            continue
        summaries.append(WarehouseSummary(name=name, total_qty=total, sku_count=len(sku_set)))

    summaries.sort(key=lambda summary: summary.total_qty, reverse=True)
    return summaries


def filter_by_warehouse(items: list[WBStockItem], warehouse_name: str | None) -> list[WBStockItem]:
    if warehouse_name is None:
        return items
    return [item for item in items if item.warehouseName == warehouse_name]


def _format_item_line(item: WBStockItem) -> str:
    return f"• {item.supplierArticle or '—'} (nm:{item.nmId}) — {item.quantity} шт."


def _sorted_positive_groups(items: list[WBStockItem]) -> list[tuple[str, list[WBStockItem]]]:
    groups: dict[str, list[WBStockItem]] = defaultdict(list)

    for item in items:
        if item.quantity <= 0:
            continue
        groups[item.warehouseName].append(item)

    sorted_groups: list[tuple[str, list[WBStockItem]]] = []
    for warehouse, group_items in groups.items():
        group_items.sort(
            key=lambda entry: (
                -entry.quantity,
                entry.supplierArticle or "",
                entry.nmId,
            )
        )
        sorted_groups.append((warehouse, group_items))

    sorted_groups.sort(key=lambda pair: pair[0])
    return sorted_groups


def build_pages_grouped_by_warehouse(
    items: list[WBStockItem], *, per_page: int = LINES_PER_PAGE
) -> PagedView:
    """Строит постраничное представление остатков по складам."""

    if per_page < 2:
        raise ValueError("per_page must allow header and at least one item")

    groups = _sorted_positive_groups(items)
    pages: list[Page] = []
    page_number = 1

    for warehouse, group_items in groups:
        index = 0
        while index < len(group_items):
            chunk = group_items[index : index + (per_page - 1)]
            lines = [f"🏬 {warehouse}"] + [_format_item_line(item) for item in chunk]
            pages.append(Page(number=page_number, lines=lines))
            page_number += 1
            index += len(chunk)

    total_items = sum(len(group) for _, group in groups)
    total_pages = len(pages)
    return PagedView(pages=pages, total_items=total_items, total_pages=total_pages)


def format_single_warehouse(
    items: list[WBStockItem], warehouse: str, *, per_page: int = LINES_PER_PAGE
) -> tuple[str, PagedView | None]:
    relevant = [item for item in items if item.warehouseName == warehouse and item.quantity > 0]

    if not relevant:
        return "Сейчас нет остатков на этом складе.", None

    sorted_items = sorted(
        relevant,
        key=lambda entry: (-entry.quantity, entry.supplierArticle or "", entry.nmId),
    )
    lines = [_format_item_line(item) for item in sorted_items]
    body = "\n".join(lines)
    preview = f"🏬 {warehouse}\n{body}" if body else f"🏬 {warehouse}"

    if len(preview) <= TELEGRAM_TEXT_LIMIT:
        return body, None

    paged_view = build_pages_grouped_by_warehouse(relevant, per_page=per_page)
    return "", paged_view


def _sort_for_export(items: list[WBStockItem]) -> list[WBStockItem]:
    return sorted(
        items,
        key=lambda entry: (
            entry.warehouseName,
            -entry.quantity,
            entry.supplierArticle or "",
            entry.nmId,
        ),
    )


def build_export_dataframe(items: list[WBStockItem]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for item in _sort_for_export(items):
        rows.append(
            {
                "Склад": item.warehouseName,
                "Артикул": item.supplierArticle,
                "nmId": item.nmId,
                "Штрихкод": item.barcode,
                "Кол-во": item.quantity,
                "Категория": item.category or "",
                "Предмет": item.subject or "",
                "Бренд": item.brand or "",
                "Размер": item.techSize or "",
                "Цена": item.price or "",
                "Скидка": item.discount or "",
            }
        )

    return pd.DataFrame(rows, columns=EXPORT_HEADERS)


def build_export_xlsx(items: list[WBStockItem]) -> bytes:
    dataframe = build_export_dataframe(items)
    return dataframe_to_xlsx_bytes(dataframe)


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w]+", "_", value, flags=re.UNICODE)
    cleaned = cleaned.strip("_")
    return cleaned or "warehouse"


def build_export_filename(view: str, warehouse: str | None, moment: datetime) -> str:
    timestamp = moment.strftime("%Y%m%d_%H%M")

    if view == "ALL":
        return f"wb_ostatki_ALL_{timestamp}.xlsx"

    if warehouse:
        sanitized = sanitize_filename(warehouse)
        return f"wb_ostatki_{sanitized}_{timestamp}.xlsx"

    return f"wb_ostatki_{timestamp}.xlsx"
