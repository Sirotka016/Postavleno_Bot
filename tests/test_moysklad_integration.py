from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import httpx
import pytest

from postavleno_bot.core.config import Settings
from postavleno_bot.integrations.moysklad import fetch_moysklad_stock_map


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = "payload"

    def json(self) -> dict[str, Any]:
        return self._payload


class DummyClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, int]] = []
        self._index = 0

    async def __aenter__(self) -> DummyClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - required by context
        return None

    async def get(self, url: str, params: dict[str, int] | None = None) -> FakeResponse:
        if params is None:
            params = {}
        self.calls.append(params)
        response = self._responses[self._index]
        self._index += 1
        return response


def test_fetch_moysklad_stock_map_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        FakeResponse(
            {"rows": [{"article": "A-1", "quantity": 5}, {"article": "B-2", "quantity": 7}]}
        ),
        FakeResponse({"rows": [{"article": "A-1", "quantity": 9}]}),
        FakeResponse({"rows": []}),
    ]
    client = DummyClient(responses)

    def fake_async_client(**kwargs: Any) -> DummyClient:
        return client

    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)

    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        MOYSKLAD_TOKEN="secret",
        MOYSKLAD_PAGE_SIZE=2,
    )

    result = asyncio.run(fetch_moysklad_stock_map(settings))

    assert result == {"A-1": Decimal("9"), "B-2": Decimal("7")}
    assert client.calls == [
        {"limit": 2, "offset": 0},
        {"limit": 2, "offset": 2},
    ]
