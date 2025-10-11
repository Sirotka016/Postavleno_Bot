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
    def __init__(self, responses: dict[str, list[DummyResponse]]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> DummyAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - required by context
        return None

    async def get(self, path: str, params: dict[str, Any] | None = None) -> DummyResponse:
        if params is None:
            params = {}
        async with self._lock:
            self.calls.append({"path": path, "params": params.copy()})
            if path == "/entity/assortment":
                filter_value = params.get("filter", "")
                _, _, article = filter_value.partition("=")
                queue = self._responses.setdefault(article, [])
                if not queue:
                    raise AssertionError(f"Unexpected request for article {article}")
                return queue.pop(0)
            raise AssertionError(f"Unexpected path: {path}")


def test_norm_article() -> None:
    assert norm_article(" артикул \t  12 ") == "АРТИКУЛ 12"
    assert norm_article("ёЛка") == "ЕЛКА"
    assert norm_article("SKU\u00a0123") == "SKU 123"


def test_fetch_quantities_for_articles_batches(monkeypatch: pytest.MonkeyPatch) -> None:
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
    client = DummyAsyncClient(responses)

    def fake_client(**kwargs: Any) -> DummyAsyncClient:
        return client

    monkeypatch.setattr(moysklad.httpx, "AsyncClient", fake_client)

    settings = Settings(TELEGRAM_BOT_TOKEN="token", MOYSKLAD_TOKEN="secret")
    wb_articles = {"A-1", "B-2", "C-3"}

    result = asyncio.run(fetch_quantities_for_articles(settings, wb_articles))

    assert result == {
        "A-1": Decimal("5"),
        "B-2": Decimal("5"),
        "C-3": Decimal("1"),
    }
    requested_articles = sorted({call["params"]["filter"].split("=")[1] for call in client.calls})
    assert requested_articles == ["A-1", "B-2", "C-3"]


def test_merge_ms_into_wb_keeps_shape() -> None:
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
