from __future__ import annotations

import base64
from decimal import Decimal
from typing import Any

import httpx

from ..core.config import Settings
from ..core.logging import get_logger

BASE_URL = "https://api.moysklad.ru/api/remap/1.2"


def build_moysklad_auth_headers(settings: Settings) -> dict[str, str]:
    mode = settings.moysklad_auth_mode
    headers: dict[str, str] = {}

    if mode == "basic":
        if not settings.moysklad_login or not settings.moysklad_password:
            raise RuntimeError("Для basic-авторизации требуется MOYSKLAD_LOGIN и MOYSKLAD_PASSWORD")
        credentials = f"{settings.moysklad_login}:{settings.moysklad_password}".encode()
        headers["Authorization"] = f"Basic {base64.b64encode(credentials).decode('ascii')}"
        return headers

    token_secret = settings.moysklad_token
    if token_secret is None:
        raise RuntimeError("Для token-авторизации необходимо указать MOYSKLAD_TOKEN")
    headers["Authorization"] = f"Bearer {token_secret.get_secret_value()}"
    return headers


async def fetch_moysklad_stock_map(settings: Settings) -> dict[str, Decimal]:
    logger = get_logger(__name__)
    auth_headers = build_moysklad_auth_headers(settings)
    page_size = settings.moysklad_page_size
    stock: dict[str, Decimal] = {}

    async with httpx.AsyncClient(
        timeout=60,
        base_url=BASE_URL,
        headers={
            "Accept-Encoding": "gzip",
            "User-Agent": "PostavlenoBot/1.0",
            **auth_headers,
        },
    ) as client:
        offset = 0
        total_rows = 0
        while True:
            params = {"limit": page_size, "offset": offset}
            logger.info("moysklad.request", offset=offset, limit=page_size)
            try:
                response = await client.get("/report/stock/all", params=params)
            except httpx.HTTPError as exc:  # pragma: no cover - defensive branch
                raise RuntimeError(f"Ошибка сети при обращении к МойСклад: {exc}") from exc

            if response.status_code >= 400:
                snippet = response.text[:200]
                raise RuntimeError(f"Ошибка МойСклад: {response.status_code} {snippet}")

            payload: dict[str, Any] = response.json()
            rows = payload.get("rows", []) or []
            logger.info("moysklad.page", offset=offset, received=len(rows))

            for row in rows:
                article = row.get("article")
                if not article:
                    continue
                quantity = row.get("quantity")
                if quantity is None:
                    continue
                stock[str(article)] = Decimal(str(quantity))
            total_rows += len(rows)

            if len(rows) < page_size:
                break
            offset += page_size

    logger.info("moysklad.done", rows_total=total_rows, articles=len(stock))
    return stock
