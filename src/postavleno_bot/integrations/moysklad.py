"""Helpers for MoySklad API."""

from __future__ import annotations

from typing import Any

from ..utils.http import create_ms_client, request_with_retry


async def fetch_ms_stocks_all(token: str) -> list[dict[str, Any]]:
    """Fetch the full stock report from MoySklad."""

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip",
    }
    items: list[dict[str, Any]] = []
    offset = 0
    limit = 1000

    async with create_ms_client(headers=headers) as client:
        while True:
            response = await request_with_retry(
                client,
                method="GET",
                path="/report/stock/all",
                logger_name="integrations.ms",
                params={"limit": limit, "offset": offset},
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("rows") if isinstance(payload, dict) else None
            if not rows:
                break
            if isinstance(rows, list):
                for entry in rows:
                    if isinstance(entry, dict):
                        items.append(entry)
            offset += limit

    return items


__all__ = ["fetch_ms_stocks_all"]
