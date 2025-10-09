from __future__ import annotations

import os
import sys
from types import SimpleNamespace

from postavleno_bot.core.config import get_settings

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "TEST:TOKEN")
get_settings.cache_clear()

if "httpx" not in sys.modules:

    class _DummyAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - helper
            pass

        async def __aenter__(self) -> _DummyAsyncClient:  # pragma: no cover
            return self

        async def __aexit__(self, *exc_info: object) -> bool:  # pragma: no cover
            return False

        async def get(self, *args: object, **kwargs: object) -> object:  # pragma: no cover
            raise RuntimeError("httpx.AsyncClient.get is not available in tests")

    sys.modules["httpx"] = SimpleNamespace(
        AsyncClient=_DummyAsyncClient,
        codes=SimpleNamespace(UNAUTHORIZED=401, TOO_MANY_REQUESTS=429),
    )
