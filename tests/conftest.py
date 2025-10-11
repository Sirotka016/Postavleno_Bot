from __future__ import annotations

import sys
from types import SimpleNamespace

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

        async def request(self, *args: object, **kwargs: object) -> object:  # pragma: no cover
            raise RuntimeError("httpx.AsyncClient.request is not available in tests")

    class _DummyTimeout:
        def __init__(self, *args: object, **kwargs: object) -> None:  # pragma: no cover
            pass

    class _DummyHTTPError(Exception):
        pass

    class _DummyHTTPStatusError(_DummyHTTPError):
        def __init__(self, message: str, *, response: object | None = None) -> None:
            super().__init__(message)
            self.response = response

    sys.modules["httpx"] = SimpleNamespace(
        AsyncClient=_DummyAsyncClient,
        HTTPError=_DummyHTTPError,
        HTTPStatusError=_DummyHTTPStatusError,
        Timeout=_DummyTimeout,
        codes=SimpleNamespace(UNAUTHORIZED=401, TOO_MANY_REQUESTS=429),
    )
