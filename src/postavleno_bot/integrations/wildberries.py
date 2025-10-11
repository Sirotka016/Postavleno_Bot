from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from ..utils.http import create_wb_client, request_with_retry


class WBApiError(RuntimeError):
    """Base exception for Wildberries API failures."""


class WBAuthError(WBApiError):
    """Raised when Wildberries rejects authentication."""


class WBRatelimitError(WBApiError):
    """Raised when Wildberries API responds with rate limit."""

    def __init__(self, message: str, *, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(slots=True)
class WBStockItem:
    lastChangeDate: datetime
    warehouseName: str
    supplierArticle: str
    nmId: int
    barcode: str
    quantity: int
    inWayToClient: int
    inWayFromClient: int
    quantityFull: int
    category: str | None
    subject: str | None
    brand: str | None
    techSize: str | None
    price: int | None
    discount: int | None
    scCode: str | None


_STOCKS_PATH = "/api/v1/supplier/stocks"

_RETRY_ATTEMPTS = 4
_RETRY_BASE_DELAY = 0.5


def _parse_datetime(value: str) -> datetime:
    if not value:
        return datetime.now(UTC)
    normalized = value.replace("Z", "+00:00")
    moment = datetime.fromisoformat(normalized)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


async def _request_page(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    params: dict[str, Any],
    page_idx: int,
) -> list[dict[str, Any]]:
    logger = structlog.get_logger(__name__).bind(endpoint=_STOCKS_PATH, page_idx=page_idx)
    try:
        response = await request_with_retry(
            client,
            method="GET",
            path=_STOCKS_PATH,
            headers=headers,
            params=params,
            logger_name=__name__,
            max_attempts=_RETRY_ATTEMPTS,
            base_delay=_RETRY_BASE_DELAY,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response else None
        if status == httpx.codes.UNAUTHORIZED:
            logger.warning("WB API authentication failed", status=status, outcome="fail")
            raise WBAuthError("WB API token rejected") from exc
        if status == httpx.codes.TOO_MANY_REQUESTS:
            retry_raw = exc.response.headers.get("Retry-After") if exc.response else None
            if not retry_raw:
                retry_raw = exc.response.headers.get("X-Ratelimit-Retry") if exc.response else None
            retry_after = int(retry_raw) if retry_raw and retry_raw.isdigit() else None
            logger.warning(
                "WB API rate limited",
                status=status,
                retry_after=retry_after,
                outcome="fail",
            )
            raise WBRatelimitError("WB API rate limit exceeded", retry_after=retry_after) from exc
        logger.error("WB API error", status=status, outcome="fail")
        raise WBApiError(f"WB API error: {status}") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - network issues
        logger.error("WB API network error", error=str(exc), outcome="fail")
        raise WBApiError("WB API network error") from exc

    payload = response.json()
    if not isinstance(payload, list):
        logger.error("Unexpected payload type", outcome="fail")
        raise WBApiError("Unexpected response structure from WB API")

    logger.info("WB API page fetched", items_count=len(payload), outcome="success")
    return payload


def _convert_item(data: dict[str, Any]) -> WBStockItem:
    return WBStockItem(
        lastChangeDate=_parse_datetime(str(data.get("lastChangeDate", ""))),
        warehouseName=str(data.get("warehouseName", "")),
        supplierArticle=str(data.get("supplierArticle", "")),
        nmId=int(data.get("nmId", 0)),
        barcode=str(data.get("barcode", "")),
        quantity=int(data.get("quantity", 0)),
        inWayToClient=int(data.get("inWayToClient", 0)),
        inWayFromClient=int(data.get("inWayFromClient", 0)),
        quantityFull=int(data.get("quantityFull", 0)),
        category=data.get("category"),
        subject=data.get("subject"),
        brand=data.get("brand"),
        techSize=data.get("techSize"),
        price=int(data["Price"]) if data.get("Price") is not None else None,
        discount=int(data["Discount"]) if data.get("Discount") is not None else None,
        scCode=data.get("SCCode"),
    )


async def fetch_stocks_all(token: str, *, date_from: datetime) -> tuple[list[WBStockItem], dict[str, Any]]:
    """Выгружает все остатки по правилам пагинации 'supplier/stocks'."""

    headers = {"Authorization": token}
    params = {"dateFrom": date_from.isoformat()}
    items: list[WBStockItem] = []

    metadata: dict[str, Any] = {}
    async with create_wb_client() as client:
        metadata = {
            "http2": bool(getattr(client, "_postavleno_http2", False)),
            "timeout_s": float(getattr(client, "_postavleno_timeout", 0.0)),
        }
        page_idx = 0
        current_date_from = params["dateFrom"]
        while True:
            payload = await _request_page(
                client,
                headers=headers,
                params={"dateFrom": current_date_from},
                page_idx=page_idx,
            )
            if not payload:
                break

            for entry in payload:
                items.append(_convert_item(entry))

            last_entry = payload[-1]
            current_date_from = str(last_entry.get("lastChangeDate", current_date_from))
            page_idx += 1

    return items, metadata
