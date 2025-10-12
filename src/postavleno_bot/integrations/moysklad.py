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
        headers=headers,
    )


async def fetch_ms_stocks_all(token: str) -> dict[str, Any]:
    """Fetch the current stock report from MoySklad with auth fallbacks."""

    async with create_ms_client() as client:
        basic_auth = httpx.BasicAuth(token, "")
        try:
            response = await _perform_request(client, auth=basic_auth)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != httpx.codes.UNAUTHORIZED:
                _log_error_response(exc.response)
                raise
            # Retry with Bearer token header as a fallback scenario.
            bearer_headers = {"Authorization": f"Bearer {token}"}
            try:
                response = await _perform_request(client, headers=bearer_headers)
            except httpx.HTTPStatusError as bearer_exc:
                _log_error_response(bearer_exc.response)
                raise

        payload = response.json()
        if isinstance(payload, Mapping):
            return dict(payload)
        return {}


__all__ = ["fetch_ms_stocks_all"]
