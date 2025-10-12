"""Helpers for MoySklad API."""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from ..core.logging import get_logger
from ..utils.http import create_ms_client, request_with_retry

_logger = get_logger("integrations.ms")


def _log_error_response(response: httpx.Response) -> None:
    try:
        body: Any = response.json()
    except Exception:  # pragma: no cover - defensive
        body = response.text
    _logger.error(
        "ms.api_failure",
        status=response.status_code,
        url=str(response.request.url),
        body=body,
    )


COMMON_MS_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Accept-Encoding": "gzip",
    "User-Agent": "PostavlenoBot/1.0",
}


async def _perform_request(
    client: httpx.AsyncClient,
    *,
    auth: httpx.Auth | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return await request_with_retry(
        client,
        method="GET",
        path="/report/stock/all/current",
        logger_name="integrations.ms",
        params={"include": "zeroLines"},
        auth=auth,
        headers=headers or COMMON_MS_HEADERS,
    )


async def fetch_ms_stocks_all(token: str) -> dict[str, Any]:
    """Fetch the current stock report from MoySklad with auth fallbacks."""

    async with create_ms_client(headers=COMMON_MS_HEADERS) as client:
        basic_auth = httpx.BasicAuth(token, "")
        try:
            response = await _perform_request(
                client,
                auth=basic_auth,
                headers=COMMON_MS_HEADERS,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != httpx.codes.UNAUTHORIZED:
                _log_error_response(exc.response)
                raise
        else:
            payload = response.json()
            return dict(payload) if isinstance(payload, Mapping) else {}

        bearer_headers = {**COMMON_MS_HEADERS, "Authorization": f"Bearer {token}"}
        try:
            response = await _perform_request(client, headers=bearer_headers)
        except httpx.HTTPStatusError as exc:
            _log_error_response(exc.response)
            raise

        payload = response.json()
        return dict(payload) if isinstance(payload, Mapping) else {}


__all__ = ["fetch_ms_stocks_all"]
