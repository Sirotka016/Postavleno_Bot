"""Helpers for Wildberries Statistics API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..core.logging import get_logger
from ..utils.http import create_wb_client, request_with_retry

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


async def fetch_wb_stocks_all(token: str, *, date_from: str = "2019-06-20T00:00:00Z") -> list[WBStockItem]:
    """Fetch all stock items available for the supplier."""

    headers = {"Authorization": token}
    items: list[WBStockItem] = []
    params: dict[str, Any] = {"dateFrom": date_from}
    last_change_marker: str | None = None

    async with create_wb_client(headers=headers) as client:
        while True:
            response = await request_with_retry(
                client,
                method="GET",
                path="/api/v1/supplier/stocks",
                logger_name="integrations.wb",
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or not payload:
                break

            batch: list[WBStockItem] = []
            for entry in payload:
                if isinstance(entry, Mapping):
                    batch.append(WBStockItem.from_api(entry))
            items.extend(batch)

            marker = None
            if isinstance(payload[-1], Mapping):
                marker = payload[-1].get("lastChangeDate")

            if not marker or marker == last_change_marker:
                break

            last_change_marker = str(marker)
            params = {"dateFrom": last_change_marker}

    _WB_LOGGER.info("stocks.fetched", count=len(items))
    return items


__all__ = ["WBStockItem", "fetch_wb_stocks_all"]
