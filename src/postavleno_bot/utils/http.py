from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

import httpx

try:  # pragma: no cover - optional dependency
    import h2  # noqa: F401

    HTTP2_AVAILABLE = True
except Exception:  # pragma: no cover - graceful fallback
    HTTP2_AVAILABLE = False

from ..core.config import get_settings
from ..core.logging import get_logger

_WB_BASE_URL = "https://statistics-api.wildberries.ru"
_MS_BASE_URL = "https://api.moysklad.ru/api/remap/1.2"


def create_wb_client(*, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    """Return a configured AsyncClient for Wildberries API."""

    settings = get_settings()
    base_headers = {"Accept-Encoding": "gzip"}
    if headers:
        base_headers.update(headers)
    client = httpx.AsyncClient(
        base_url=_WB_BASE_URL,
        headers=base_headers,
        http2=HTTP2_AVAILABLE,
        timeout=settings.http_timeout_s,
    )
    client._postavleno_timeout = settings.http_timeout_s  # type: ignore[attr-defined]
    return client


def create_ms_client(*, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    """Return a configured AsyncClient for MoySklad API."""

    settings = get_settings()
    base_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": "PostavlenoBot/1.0",
    }
    if headers:
        base_headers.update(headers)
    client = httpx.AsyncClient(
        base_url=_MS_BASE_URL,
        headers=base_headers,
        http2=HTTP2_AVAILABLE,
        timeout=settings.http_timeout_s,
    )
    client._postavleno_timeout = settings.http_timeout_s  # type: ignore[attr-defined]
    return client


async def request_with_retry(
    client: httpx.AsyncClient,
    *,
    method: str,
    url: str | None = None,
    path: str | None = None,
    logger_name: str,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    backoff_factor: float = 2.0,
    retry_for_statuses: Iterable[int] = (httpx.codes.TOO_MANY_REQUESTS,),
    **request_kwargs: Any,
) -> httpx.Response:
    """Execute HTTP request with exponential backoff and logging."""

    if url and path:
        raise ValueError("Specify either 'url' or 'path', not both")

    target = url or path
    if target is None:
        raise ValueError("Target URL or path must be provided")
    target_url = target

    logger = get_logger(logger_name)
    delay = base_delay
    retry_statuses = set(retry_for_statuses)
    attempt = 1

    while attempt <= max_attempts:
        logger.debug(
            "http.request",
            method=method,
            target=target,
            attempt=attempt,
            outcome="attempt",
        )
        try:
            response = await client.request(method, target_url, **request_kwargs)
        except httpx.HTTPError as exc:
            logger.warning(
                "http.error",
                method=method,
                target=target,
                attempt=attempt,
                error=str(exc),
                outcome="error",
            )
            if attempt >= max_attempts:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * backoff_factor, 60.0)
            attempt += 1
            continue

        status = response.status_code
        response_url = str(response.request.url)
        if status in retry_statuses or status >= 500:
            retry_after_header = None
            if status == httpx.codes.TOO_MANY_REQUESTS:
                retry_after_header = response.headers.get("Retry-After")
            logger.warning(
                "http.retry",
                method=method,
                target=target,
                url=response_url,
                attempt=attempt,
                status=status,
                retry_after=retry_after_header,
                outcome="retry",
            )
            if attempt >= max_attempts:
                response.raise_for_status()
            if retry_after_header:
                try:
                    retry_after = float(retry_after_header)
                except (TypeError, ValueError):
                    retry_after = delay
                else:
                    retry_after = max(delay, retry_after)
            else:
                retry_after = delay
            await asyncio.sleep(retry_after)
            delay = min(delay * backoff_factor, 60.0)
            attempt += 1
            continue

        if not response.is_success:
            preview = ""
            try:
                preview = response.text[:2048]
            except Exception:  # pragma: no cover - defensive
                preview = "<unavailable>"
            logger.error(
                "http.failure",
                method=method,
                target=target,
                url=response_url,
                status=status,
                body_preview=preview,
                outcome="fail",
            )
            response.raise_for_status()

        logger.info(
            "http.success",
            method=method,
            target=target,
            url=response_url,
            status=status,
            attempt=attempt,
            outcome="success",
        )
        return response

    raise RuntimeError("HTTP request retry loop exhausted")
