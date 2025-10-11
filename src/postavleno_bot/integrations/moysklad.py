from __future__ import annotations

import asyncio
import base64
import re
import unicodedata
from collections.abc import Iterable
from contextlib import suppress
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from ..core.config import Settings
from ..core.logging import get_logger

BASE_URL = "https://api.moysklad.ru/api/remap/1.2"
_USER_AGENT = "PostavlenoBot/1.0"
_MAX_CONCURRENT_REQUESTS = 6
_BATCH_SIZE = 50
_MAX_RETRIES = 5
_BACKOFF_BASE = 1.5


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


def _create_client(settings: Settings, headers: dict[str, str]) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=60,
        base_url=BASE_URL,
        headers={
            "Accept-Encoding": "gzip",
            "User-Agent": _USER_AGENT,
            **headers,
        },
    )


async def _request_with_retry(
    client: httpx.AsyncClient,
    *,
    path: str,
    params: dict[str, Any],
    logger_name: str,
) -> httpx.Response:
    logger = get_logger(logger_name)
    delay = 1.0
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.debug("moysklad.request", path=path, attempt=attempt, delay=round(delay, 2))
            response = await client.get(path, params=params)
        except httpx.HTTPError as exc:
            if attempt == _MAX_RETRIES:
                raise RuntimeError(f"Ошибка сети при обращении к МойСклад: {exc}") from exc
            await asyncio.sleep(delay)
            delay = min(delay * _BACKOFF_BASE, 30.0)
            continue

        if response.status_code == 429 or response.status_code >= 500:
            if attempt == _MAX_RETRIES:
                snippet = response.text[:200]
                raise RuntimeError(
                    f"Ошибка МойСклад: {response.status_code} {snippet} (после {_MAX_RETRIES} попыток)"
                )
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                with suppress(ValueError):
                    delay = max(delay, float(retry_after))
            await asyncio.sleep(delay)
            delay = min(delay * _BACKOFF_BASE, 60.0)
            continue

        if response.status_code >= 400:
            snippet = response.text[:200]
            raise RuntimeError(f"Ошибка МойСклад: {response.status_code} {snippet}")

        return response

    raise RuntimeError("Не удалось получить ответ от МойСклад")


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
) -> dict[str, Decimal]:
    params = {"filter": f"article={article}"}
    async with semaphore:
        response = await _request_with_retry(
            client,
            path="/entity/assortment",
            params=params,
            logger_name=__name__,
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


def _chunked(iterable: Iterable[str], size: int) -> Iterable[list[str]]:
    iterator = iter(iterable)
    while True:
        chunk: list[str] = []
        for _ in range(size):
            try:
                chunk.append(next(iterator))
            except StopIteration:
                break
        if not chunk:
            break
        yield chunk


async def _fetch_strategy_batch(
    settings: Settings,
    normalized_articles: set[str],
) -> dict[str, Decimal]:
    headers = build_ms_headers(settings)
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)
    results: dict[str, Decimal] = {}
    async with _create_client(settings, headers) as client:
        ordered = sorted(normalized_articles)
        for chunk in _chunked(ordered, _BATCH_SIZE):
            tasks = [
                _fetch_article(
                    client,
                    article=article,
                    quantity_field=settings.moysklad_quantity_field,
                    allowed_articles=normalized_articles,
                    semaphore=semaphore,
                )
                for article in chunk
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for response in responses:
                if isinstance(response, BaseException):
                    raise response
                for key, value in response.items():
                    results[key] = results.get(key, Decimal("0")) + value
    return results


async def _fetch_strategy_scan(
    settings: Settings,
    normalized_articles: set[str],
) -> dict[str, Decimal]:
    headers = build_ms_headers(settings)
    quantity_field = settings.moysklad_quantity_field
    results: dict[str, Decimal] = {}
    limit = max(1, settings.moysklad_page_size)
    offset = 0

    async with _create_client(settings, headers) as client:
        while True:
            params = {"limit": limit, "offset": offset}
            response = await _request_with_retry(
                client,
                path="/report/stock/all",
                params=params,
                logger_name=__name__,
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
    return results


async def fetch_quantities_for_articles(
    settings: Settings,
    wb_articles: set[str],
) -> dict[str, Decimal]:
    """Fetch MoySklad quantities strictly for the provided Wildberries articles."""

    logger = get_logger(__name__)
    normalized = {norm_article(article) for article in wb_articles if article.strip()}
    normalized.discard("")

    if not normalized:
        logger.info("moysklad.fetch.skip", reason="empty_articles")
        return {}

    strategy = "batch"
    try:
        results = await _fetch_strategy_batch(settings, normalized)
    except Exception as error:
        logger.warning("moysklad.batch_failed", error=str(error))
        strategy = "scan"
        results = await _fetch_strategy_scan(settings, normalized)

    requested = len(normalized)
    found = len(results)
    missing = max(requested - found, 0)
    logger.info(
        "moysklad.fetch.done",
        strategy=strategy,
        requested=requested,
        found=found,
        missing=missing,
    )
    return results
