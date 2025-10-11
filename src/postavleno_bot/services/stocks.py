from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog

from ..integrations.wildberries import WBStockItem, fetch_stocks_all

_CACHE_TTL = timedelta(minutes=3)
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

_cache: dict[tuple[str, str, str], _CacheEntry] = {}
_logger = structlog.get_logger(__name__)


def _make_cache_key(token: str, date_from: datetime) -> tuple[str, str, str]:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return ("stocks", date_from.isoformat(), token_hash)


async def get_stock_data(token: str, *, force_refresh: bool = False) -> list[WBStockItem]:
    """Кэширует результаты. При force_refresh игнорирует TTL, но уважает rate-limit."""

    now = datetime.now(UTC)
    date_from = _INITIAL_DATE_FROM
    key = _make_cache_key(token, date_from)
    entry = _cache.get(key)

    if entry and entry.expires_at > now and not force_refresh:
        _logger.info(
            "wb.fetch",
            outcome="cache",
            cache_hit=True,
            rows=len(entry.items),
        )
        return entry.items

    if entry and force_refresh and now - entry.fetched_at < _RATE_LIMIT_WINDOW:
        _logger.warning(
            "wb.fetch",
            outcome="throttled",
            cache_hit=True,
            rows=len(entry.items),
        )
        return entry.items

    items = await fetch_stocks_all(token, date_from=date_from)
    expires_at = now + _CACHE_TTL
    _cache[key] = _CacheEntry(items=items, fetched_at=now, expires_at=expires_at)
    _logger.info("wb.fetch", outcome="success", cache_hit=False, rows=len(items))
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


