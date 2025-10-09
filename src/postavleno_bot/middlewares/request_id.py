from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class RequestIdMiddleware(BaseMiddleware):
    """Attach request ID and timing information to each update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        request_id = uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        data["request_id"] = request_id
        start_time = time.perf_counter()
        data["started_at"] = start_time
        try:
            return await handler(event, data)
        finally:
            for key in ("latency_ms", "request_id"):
                with suppress(LookupError):
                    structlog.contextvars.unbind_contextvars(key)
