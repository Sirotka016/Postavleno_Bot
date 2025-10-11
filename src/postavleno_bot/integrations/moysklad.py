from __future__ import annotations

import asyncio

import base64
import re
import unicodedata
from contextlib import suppress
from decimal import Decimal, InvalidOperation
from itertools import islice
from typing import Any, Iterable

import httpx

from ..core.config import Settings
from ..core.logging import get_logger
from ..utils.http import create_ms_client, request_with_retry

_BATCH_SIZE = 50


def build_ms_headers(settings: Settings) -> dict[str, str]:
    """Build Authorization headers for MoySklad API."""

    mode = settings.moysklad_auth_mode
    if mode == "basic":
        if not settings.moysklad_login or not settings.moysklad_password:
            raise RuntimeError(
                "Для basic-авторизации необходимо задать MOYSKLAD_LOGIN и MOYSKLAD_PASSWORD"
            )
        credentials = f"{settings.moysklad_login}:{settings.moysklad_password}".encode()
        token = base64.b64encode(credentials).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    token_secret = settings.moysklad_token
    if token_secret is None:
        raise RuntimeError("Для token-авторизации необходимо указать MOYSKLAD_TOKEN")
    return {"Authorization": f"Bearer {token_secret.get_secret_value()}"}


_WS_RE = re.compile(r"\s+")


def norm_article(raw: str) -> str:
    """Normalise article code for reliable comparisons."""

    value = unicodedata.normalize("NFKC", raw.strip())
    value = _WS_RE.sub(" ", value.upper())
    value = value.replace("Ё", "Е")
    return value


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    iterator = iter(items)
    while True:
        chunk = list(islice(iterator, size))
        if not chunk:
            break
        yield chunk


def _accumulate_row(
    store: dict[str, Decimal],
    row: dict[str, Any],
    *,
    quantity_field: str,
    allowed_articles: set[str],
) -> None:
    article = row.get("article")
    if not article:
        return
    normalized = norm_article(str(article))
    if normalized not in allowed_articles:
        return
    raw_quantity = row.get(quantity_field)
    if raw_quantity is None:
        return
    try:
        quantity = Decimal(str(raw_quantity))
    except (InvalidOperation, TypeError):  # pragma: no cover - defensive
        return
    store[normalized] = store.get(normalized, Decimal("0")) + quantity


async def _fetch_article(
    client: httpx.AsyncClient,
    *,
    article: str,
    quantity_field: str,
    allowed_articles: set[str],
    semaphore: asyncio.Semaphore,
    attempts: int,
    base_delay: float,
) -> dict[str, Decimal]:
    params = {"filter": f"article={article}"}
    async with semaphore:
        response = await request_with_retry(
            client,
            method="GET",
            path="/entity/assortment",
            params=params,
            logger_name=__name__,
            max_attempts=attempts,
            base_delay=base_delay,
        )
    payload: dict[str, Any] = response.json()
    rows = payload.get("rows", []) or []
    result: dict[str, Decimal] = {}
    for row in rows:
        if isinstance(row, dict):
            _accumulate_row(
                result,
                row,
                quantity_field=quantity_field,
                allowed_articles=allowed_articles,
            )
    return result


async def _fetch_strategy_batch(
    settings: Settings,
    normalized_articles: set[str],
) -> tuple[dict[str, Decimal], dict[str, Any]]:
    headers = build_ms_headers(settings)
    concurrency = max(1, settings.moysklad_max_concurrency)
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, Decimal] = {}
    articles = sorted(normalized_articles)
    batches = _chunked(articles, _BATCH_SIZE)
    logger = get_logger(__name__)

    metadata: dict[str, Any] = {}
    async with create_ms_client(headers=headers) as client:
        metadata = {
            "http2": bool(getattr(client, "_postavleno_http2", False)),
            "timeout_s": float(getattr(client, "_postavleno_timeout", settings.http_timeout_s)),
        }
        for batch in batches:
            logger.info(
                "ms.batch",
                size=len(batch),
                concurrency=concurrency,
                outcome="start",
            )
            tasks = [
                asyncio.create_task(
                    _fetch_article(
                        client,
                        article=article,
                        quantity_field=settings.moysklad_quantity_field,
                        allowed_articles=normalized_articles,
                        semaphore=semaphore,
                        attempts=settings.moysklad_retry_attempts,
                        base_delay=settings.moysklad_retry_base_delay,
                    )
                )
                for article in batch
            ]
            batch_results = await asyncio.gather(*tasks)
            logger.info(
                "ms.batch",
                size=len(batch),
                concurrency=concurrency,
                outcome="success",
            )
            for response in batch_results:
                for key, value in response.items():
                    results[key] = results.get(key, Decimal("0")) + value
    return results, metadata


async def _fetch_strategy_scan(
    settings: Settings,
    normalized_articles: set[str],
) -> tuple[dict[str, Decimal], dict[str, Any]]:
    headers = build_ms_headers(settings)
    quantity_field = settings.moysklad_quantity_field
    results: dict[str, Decimal] = {}
    limit = max(1, settings.moysklad_page_size)
    offset = 0

    metadata: dict[str, Any] = {}
    async with create_ms_client(headers=headers) as client:
        metadata = {
            "http2": bool(getattr(client, "_postavleno_http2", False)),
            "timeout_s": float(getattr(client, "_postavleno_timeout", settings.http_timeout_s)),
        }
        while True:
            params = {"limit": limit, "offset": offset}
            response = await request_with_retry(
                client,
                method="GET",
                path="/report/stock/all",
                params=params,
                logger_name=__name__,
                max_attempts=settings.moysklad_retry_attempts,
                base_delay=settings.moysklad_retry_base_delay,
            )
            payload: dict[str, Any] = response.json()
            rows = payload.get("rows", []) or []
            for row in rows:
                if isinstance(row, dict):
                    _accumulate_row(
                        results,
                        row,
                        quantity_field=quantity_field,
                        allowed_articles=normalized_articles,
                    )
            if len(rows) < limit:
                break
            offset += limit
    return results, metadata


async def fetch_quantities_for_articles(
    settings: Settings,
    wb_articles: set[str],
) -> dict[str, Decimal]:
    """Fetch MoySklad quantities strictly for the provided Wildberries articles."""

    logger = get_logger(__name__)
    normalized = {norm_article(article) for article in wb_articles if article.strip()}
    normalized.discard("")

    requested = len(normalized)
    logger.info("ms.fetch.start", outcome="start", requested=requested)

    if not normalized:
        logger.info(
            "ms.fetch.done",
            outcome="success",
            strategy="skip",
            requested=0,
            found=0,
            missing=0,
            http2=False,
            timeout_s=settings.http_timeout_s,
        )
        return {}

    strategy = "batch"
    http_metadata = {"http2": False, "timeout_s": settings.http_timeout_s}
    try:
        results, http_metadata = await _fetch_strategy_batch(settings, normalized)
    except Exception as error:
        logger.warning(
            "ms.fetch.fallback",
            outcome="fallback",
            error=str(error),
            strategy="batch",
        )
        strategy = "scan"
        results, http_metadata = await _fetch_strategy_scan(settings, normalized)

    found = len(results)
    missing = max(requested - found, 0)
    logger.info(
        "ms.fetch.done",
        outcome="success",
        strategy=strategy,
        requested=requested,
        found=found,
        missing=missing,
        http2=bool(http_metadata.get("http2", False)),
        timeout_s=float(http_metadata.get("timeout_s", settings.http_timeout_s)),
    )
    return results
