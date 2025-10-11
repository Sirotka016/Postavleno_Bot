from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from structlog.testing import capture_logs

from postavleno_bot.utils import http


def test_create_wb_client_http2_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(http2_enabled=False, http_timeout_s=12.5)
    monkeypatch.setattr(http, "get_settings", lambda: settings)

    async def _run() -> None:
        async with http.create_wb_client() as client:
            assert getattr(client, "_postavleno_http2") is False
            assert getattr(client, "_postavleno_timeout") == pytest.approx(settings.http_timeout_s)

    asyncio.run(_run())


def test_create_wb_client_http2_requested_but_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(http2_enabled=True, http_timeout_s=9.0)
    monkeypatch.setattr(http, "get_settings", lambda: settings)
    monkeypatch.setattr(http, "_http2_available", lambda: False)

    async def _run() -> list[dict[str, object]]:
        with capture_logs() as logs:
            async with http.create_wb_client() as client:
                assert getattr(client, "_postavleno_http2") is False
        return logs

    logs = asyncio.run(_run())
    assert any(
        entry.get("event") == "http2.requested_but_unavailable" and entry.get("outcome") == "fallback_to_http1"
        for entry in logs
    )


def test_create_wb_client_http2_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(http2_enabled=True, http_timeout_s=15.0)
    monkeypatch.setattr(http, "get_settings", lambda: settings)
    monkeypatch.setattr(http, "_http2_available", lambda: True)

    async def _run() -> None:
        async with http.create_wb_client() as client:
            assert getattr(client, "_postavleno_http2") is True
            assert getattr(client, "_postavleno_timeout") == pytest.approx(settings.http_timeout_s)

    asyncio.run(_run())
