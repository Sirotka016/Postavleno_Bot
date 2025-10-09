from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog

from ..integrations.wb_client import WBStockItem, fetch_stocks_all

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
