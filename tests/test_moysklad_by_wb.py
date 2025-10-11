from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest

from postavleno_bot.core.config import Settings
from postavleno_bot.integrations import moysklad
from postavleno_bot.integrations.moysklad import (
    fetch_quantities_for_articles,
    norm_article,
)
from postavleno_bot.services.store_stock_merge import merge_ms_into_wb


class DummyResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.text = "payload"

    def json(self) -> dict[str, Any]:
        return self._payload


class DummyAsyncClient:
    def __init__(self, responses: dict[str, list[DummyResponse]], *, delay: float = 0.0) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []
        self._delay = delay
        self.max_parallel = 0
        self._active = 0
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> DummyAsyncClient:  # pragma: no cover - context helper
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - context helper
        return None

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        **_: Any,
    ) -> DummyResponse:
        if params is None:
            params = {}
        filter_value = params.get("filter", "")
        _, _, article = filter_value.partition("=")
        queue = self._responses.setdefault(article, [])
        if not queue:
            raise AssertionError(f"Unexpected request for article {article}")
        async with self._lock:
            self._active += 1
            self.max_parallel = max(self.max_parallel, self._active)
        try:
            if self._delay:
                await asyncio.sleep(self._delay)
            response = queue.pop(0)
            self.calls.append({"path": path, "params": params.copy()})
            return response
        finally:
            async with self._lock:
                self._active -= 1


def test_norm_article() -> None:
    assert norm_article(" артикул \t  12 ") == "АРТИКУЛ 12"
    assert norm_article("ёЛка") == "ЕЛКА"
    assert norm_article("SKU\u00a0123") == "SKU 123"


def test_ms_fetch_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        "A-1": [
            DummyResponse(
                {"rows": [{"article": "A-1", "quantity": 3}, {"article": "A-1", "quantity": 2}]}
            ),
        ],
        "B-2": [
            DummyResponse(
                {
                    "rows": [
                        {"article": "B-2", "quantity": 5},
                        {"article": "Z-9", "quantity": 99},
                    ]
                }
            )
        ],
        "C-3": [
            DummyResponse(
                {"rows": [{"article": "C-3", "quantity": 0}, {"article": "C-3", "quantity": 1}]}
            ),
        ],
    }
    client = DummyAsyncClient(responses, delay=0.01)

    monkeypatch.setattr(moysklad, "create_ms_client", lambda **_: client)

    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        MOYSKLAD_TOKEN="secret",
        MOYSKLAD_MAX_CONCURRENCY=2,
    )
    wb_articles = {"A-1", "B-2", "C-3", "A-1"}

    result = asyncio.run(fetch_quantities_for_articles(settings, wb_articles))

    assert result == {
        "A-1": Decimal("5"),
        "B-2": Decimal("5"),
        "C-3": Decimal("1"),
    }
    requested_articles = sorted({call["params"]["filter"].split("=")[1] for call in client.calls})
    assert requested_articles == ["A-1", "B-2", "C-3"]
    assert 1 < client.max_parallel <= settings.moysklad_max_concurrency


def test_ms_by_wb_simple(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        "A-1": [
            DummyResponse(
                {"rows": [{"article": "A-1", "quantity": 1}, {"article": "A-1", "quantity": 2}]}
            )
        ],
        "B-2": [
            DummyResponse(
                {"rows": [{"article": "B-2", "quantity": 5}, {"article": "B-2", "quantity": 3}]}
            )
        ],
        "C-3": [DummyResponse({"rows": []})],
    }
    client = DummyAsyncClient(responses, delay=0.0)
    monkeypatch.setattr(moysklad, "create_ms_client", lambda **_: client)

    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        MOYSKLAD_TOKEN="secret",
        LOCAL_STORE_NAME="FootballShop",
    )

    wb_df = pd.DataFrame(
        {
            "Склад": ["WB-1", "WB-2", "WB-3", "WB-4"],
            "Артикул": ["A-1", "B-2", "C-3", "A-1"],
            "Кол-во": [10, 20, 30, 40],
        }
    )

    ms_map = asyncio.run(fetch_quantities_for_articles(settings, set(wb_df["Артикул"])))

    merged = merge_ms_into_wb(
        wb_df,
        ms_map,
        store_name=settings.local_store_name or "FootballShop",
        qty_col="Кол-во",
        art_col="Артикул",
        warehouse_col="Склад",
    )

    assert list(merged["Артикул"]) == list(wb_df["Артикул"])
    assert list(merged["Кол-во"]) == [3, 8, 30, 3]
    assert list(merged["Склад"]) == ["FootballShop"] * len(wb_df)

    filters = [call["params"]["filter"] for call in client.calls]
    assert filters == ["article=A-1", "article=B-2", "article=C-3"]


def test_store_merge_preserves_shape() -> None:
    wb_df = pd.DataFrame(
        {
            "Склад": ["WB-1", "WB-2"],
            "Артикул": ["A-1", "B-2"],
            "Кол-во": [3, 4],
            "Цена": [100, 200],
        }
    )
    ms_map = {"a-1": Decimal("7"), "B-2": Decimal("8")}

    merged = merge_ms_into_wb(
        wb_df,
        ms_map,
        store_name="FootballShop",
        qty_col="Кол-во",
        art_col="Артикул",
        warehouse_col="Склад",
    )

    assert list(merged.columns) == list(wb_df.columns)
    assert list(merged["Склад"]) == ["FootballShop", "FootballShop"]
    assert list(merged["Кол-во"]) == [7, 8]
    assert list(merged["Артикул"]) == ["A-1", "B-2"]
    assert list(merged["Цена"]) == [100, 200]


def test_missing_article_keeps_wb_qty() -> None:
    wb_df = pd.DataFrame(
        {
            "Склад": ["WB"],
            "Артикул": ["Z-9"],
            "Кол-во": [5],
        }
    )
    merged = merge_ms_into_wb(
        wb_df,
        {},
        store_name="Local",
        qty_col="Кол-во",
        art_col="Артикул",
        warehouse_col="Склад",
    )
    assert list(merged["Кол-во"]) == [5]
    assert list(merged["Склад"]) == ["Local"]
