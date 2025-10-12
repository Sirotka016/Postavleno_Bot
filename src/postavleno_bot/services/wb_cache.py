from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from ..core.config import get_settings
from ..core.logging import get_logger
from ..integrations import fetch_wb_stocks_all
from ..integrations.wildberries import WBStockItem

_logger = get_logger("stocks.cache")

_BASELINE = datetime(2019, 6, 20, tzinfo=UTC)


def _cache_dir(login: str) -> Path:
    base = get_settings().accounts_dir / login / "cache"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _cache_path(login: str) -> Path:
    return _cache_dir(login) / "wb_stocks.json"


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:  # pragma: no cover - defensive
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _item_key(payload: Mapping[str, Any]) -> str:
    supplier = str(payload.get("supplierArticle") or "").strip()
    nm_id = str(payload.get("nmId") or "").strip()
    barcode = str(payload.get("barcode") or "").strip()
    warehouse = ""
    for key in ("warehouseName", "warehouse", "warehouse_name", "officeName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            warehouse = value.strip()
            break
    return "|".join([supplier, nm_id, barcode, warehouse])


@dataclass(slots=True)
class WBCache:
    items: dict[str, dict[str, Any]]
    last_sync_at: datetime | None
    path: Path

    @classmethod
    def load(cls, login: str) -> "WBCache":
        path = _cache_path(login)
        if not path.exists():
            return cls(items={}, last_sync_at=None, path=path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_items = payload.get("items") or []
        mapped: dict[str, dict[str, Any]] = {}
        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            key = _item_key(entry)
            mapped[key] = dict(entry)
        last_sync = _parse_datetime(payload.get("last_sync_at"))
        return cls(items=mapped, last_sync_at=last_sync, path=path)

    def save(self) -> None:
        serializable = {
            "last_sync_at": _format_datetime(self.last_sync_at),
            "items": [self.items[key] for key in sorted(self.items)],
        }
        self.path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def update_with(self, entries: Iterable[WBStockItem]) -> int:
        inserted = 0
        for item in entries:
            payload = item.to_dict()
            key = _item_key(payload)
            if key not in self.items:
                inserted += 1
            self.items[key] = payload
        return inserted

    def rows(self) -> list[dict[str, Any]]:
        return [self.items[key] for key in sorted(self.items)]


def _calc_date_from(last_sync_at: datetime | None) -> datetime:
    if last_sync_at is None:
        return _BASELINE
    candidate = last_sync_at - timedelta(days=1)
    if candidate < _BASELINE:
        return _BASELINE
    return candidate


async def load_wb_rows(login: str, token: str) -> list[dict[str, Any]]:
    cache = WBCache.load(login)
    date_from_dt = _calc_date_from(cache.last_sync_at)
    date_from = date_from_dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    items, last_change = await fetch_wb_stocks_all(token, date_from=date_from)

    updated = False
    if items:
        inserted = cache.update_with(items)
        updated = True
        _logger.info(
            "cache.merge",
            login=login,
            fetched=len(items),
            inserted=inserted,
            total=len(cache.items),
            date_from=date_from,
        )
    if last_change and (cache.last_sync_at is None or last_change > cache.last_sync_at):
        cache.last_sync_at = last_change
        updated = True

    if updated or not cache.path.exists():
        cache.save()

    return cache.rows()


__all__ = ["load_wb_rows"]
