"""Helpers for MoySklad API."""

from __future__ import annotations

from typing import Any, Mapping

from ..utils.http import create_ms_client, request_with_retry


async def fetch_ms_stocks_all(token: str) -> dict[str, Any]:
    """Fetch the short stock report from MoySklad."""

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip",
    }

    async with create_ms_client(headers=headers) as client:
        response = await request_with_retry(
            client,
            method="GET",
            path="/report/stock/all/current",
            logger_name="integrations.ms",
            params={"include": "zeroLines"},
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, Mapping):
            return dict(payload)
    return {}


__all__ = ["fetch_ms_stocks_all"]
