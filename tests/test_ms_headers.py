import asyncio

import httpx

from postavleno_bot.integrations import moysklad
from postavleno_bot.integrations.moysklad import fetch_ms_stocks_all


def test_ms_uses_accept_header(monkeypatch) -> None:
    calls: list[dict[str, str]] = []

    async def fake_request_with_retry(*args, **kwargs):
        headers = kwargs.get("headers", {})
        calls.append(headers)
        assert headers.get("Accept") == "application/json"
        if len(calls) == 1:
            response = httpx.Response(
                401,
                request=httpx.Request("GET", "https://api.moysklad.ru/report"),
                json={"errors": []},
            )
            raise httpx.HTTPStatusError("unauthorized", request=response.request, response=response)
        return httpx.Response(200, json={"rows": []})

    monkeypatch.setattr(moysklad, "request_with_retry", fake_request_with_retry)

    result = asyncio.run(fetch_ms_stocks_all("token123"))
    assert result == {"rows": []}
    assert calls, "Expected at least one HTTP request"
