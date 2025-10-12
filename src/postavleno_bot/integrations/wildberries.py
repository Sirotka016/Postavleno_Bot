"""Helpers for Wildberries Statistics API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import orjson

from ..core.logging import get_logger
from ..utils.http import get_wb_client, request_with_retry

_WB_LOGGER = get_logger("integrations.wb")


@dataclass(slots=True)
class WBStockItem:
    """Representation of a single stock item returned by the WB API."""

    payload: dict[str, Any]

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> WBStockItem:
        return cls(payload=dict(data))

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        return self.payload.get(key, default)

    @property
    def warehouse_name(self) -> str | None:
        for key in ("warehouseName", "warehouse", "warehouse_name", "officeName"):
            value = self.payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @property
    def supplier_article(self) -> str | None:
        value = self.payload.get("supplierArticle")
        return str(value) if value is not None else None

    @property
    def quantity(self) -> float:
        for key in ("quantity", "stock", "stocks", "qty", "amount"):
            value = self.payload.get(key)
            if value is None:
                continue
            if isinstance(value, int | float):
                return float(value)
            try:
                return float(str(value))
            except (TypeError, ValueError):  # pragma: no cover - defensive
                continue
        return 0.0

    @property
    def last_change_at(self) -> datetime | None:
        raw = self.payload.get("lastChangeDate")
        if raw is None:
            return None
        text = str(raw).strip()
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


async def fetch_wb_stocks_all(
    token: str,
    *,
    date_from: str = "2019-06-20T00:00:00Z",
) -> tuple[list[WBStockItem], datetime | None]:
    """Fetch stock items from Wildberries with a single incremental request."""

    client = get_wb_client()
    params: dict[str, Any] = {"dateFrom": date_from}
    response = await request_with_retry(
        client,
        method="GET",
        path="/api/v1/supplier/stocks",
        logger_name="integrations.wb",
        params=params,
        headers={"Authorization": token},
    )
    response.raise_for_status()

    payload_raw = response.content
    payload = orjson.loads(payload_raw)

    items: list[WBStockItem] = []
    last_change: datetime | None = None
    if isinstance(payload, list):
        for entry in payload:
            if not isinstance(entry, Mapping):
                continue
            item = WBStockItem.from_api(entry)
            items.append(item)
            last_change_candidate = item.last_change_at
            if last_change_candidate and (last_change is None or last_change_candidate > last_change):
                last_change = last_change_candidate

    _WB_LOGGER.info(
        "stocks.fetched",
        count=len(items),
        date_from=date_from,
        last_change=last_change.isoformat() if last_change else None,
    )
    return items, last_change


__all__ = ["WBStockItem", "fetch_wb_stocks_all"]
