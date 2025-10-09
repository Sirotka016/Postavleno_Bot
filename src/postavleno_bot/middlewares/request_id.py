from __future__ import annotations

import time
import uuid
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
import structlog


class RequestIdMiddleware(BaseMiddleware):
    """Attach request ID and timing information to each update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        request_id = uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        data["request_id"] = request_id
        start_time = time.perf_counter()
        data["started_at"] = start_time
        try:
            return await handler(event, data)
        finally:
            try:
                structlog.contextvars.unbind_contextvars("request_id", "latency_ms")
            except LookupError:
                structlog.contextvars.clear_contextvars()
