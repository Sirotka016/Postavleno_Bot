from __future__ import annotations

import asyncio
from collections.abc import Iterable
from functools import lru_cache
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
_WB_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=5.0, pool=5.0)


@lru_cache(maxsize=1)
def get_wb_client() -> httpx.AsyncClient:
    """Return a cached AsyncClient for Wildberries API calls."""

    get_settings()  # ensure directories are initialized
    client = httpx.AsyncClient(
        base_url=_WB_BASE_URL,
        headers={"Accept-Encoding": "gzip"},
        http2=HTTP2_AVAILABLE,
        timeout=_WB_TIMEOUT,
    )
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
