from __future__ import annotations

import logging
import os
from collections.abc import MutableMapping
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, cast

import structlog
from rich.console import Console
from rich.logging import RichHandler
from structlog.typing import Processor

try:  # pragma: no cover - optional dependency branch
    import orjson as json_impl

    def json_dumps(obj: Any) -> bytes:
        return json_impl.dumps(obj, option=json_impl.OPT_APPEND_NEWLINE)

except Exception:  # pragma: no cover - fallback for environments without orjson
    import json as json_impl

    def json_dumps(obj: Any) -> bytes:
        return json_impl.dumps(obj, ensure_ascii=False).encode() + b"\n"


def _sanitize_fields(
    _: structlog.types.WrappedLogger,
    __: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    if "result" in event_dict:
        event_dict["outcome"] = event_dict.pop("result")
    return event_dict


_LOG_LEVEL_EMOJI = {
    "debug": "🔍",
    "info": "🟢",
    "warning": "🟡",
    "error": "🔴",
    "exception": "🔴",
    "critical": "🔴",
}

_JSON_FIELDS = (
    "chat_id",
    "user_id",
    "update_type",
    "action",
    "request_id",
    "latency_ms",
    "exception",
    "stack",
)


def _default_field_enricher(
    _: structlog.types.WrappedLogger, __: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for field in _JSON_FIELDS:
        event_dict.setdefault(field, None)
    event_dict.setdefault("msg", event_dict.get("event"))
    event_dict.setdefault("logger", event_dict.get("logger", "app"))
    return event_dict


def _event_to_message(
    _: structlog.types.WrappedLogger, __: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    if "event" in event_dict and event_dict.get("msg") is None:
        event_dict["msg"] = event_dict.pop("event")
    return event_dict


def _console_renderer(
    _: structlog.types.WrappedLogger, __: str, event_dict: MutableMapping[str, Any]
) -> str:
    level = str(event_dict.get("level", "info")).lower()
    emoji = _LOG_LEVEL_EMOJI.get(level, "🟢")
    timestamp = event_dict.get("ts", "")
    logger_name = event_dict.get("logger", "app")
    message = event_dict.get("msg", "")
    context_parts: list[str] = []
    for key in ("chat_id", "user_id", "action", "update_type", "request_id"):
        value = event_dict.get(key)
        if value is not None:
            context_parts.append(f"{key}={value}")
    context = f" [{' | '.join(context_parts)}]" if context_parts else ""
    return f"{timestamp} {emoji} {logger_name}: {message}{context}"


def _json_renderer(
    _: structlog.types.WrappedLogger, __: str, event_dict: MutableMapping[str, Any]
) -> str:
    return json_dumps(event_dict).decode()


def _create_rich_handler() -> RichHandler:
    return RichHandler(
        console=Console(force_terminal=True),
        rich_tracebacks=True,
        markup=True,
        show_path=False,
        log_time_format="%Y-%m-%d %H:%M:%S",
    )


def _create_file_handler(log_dir: Path) -> TimedRotatingFileHandler:
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        log_dir / "app.json",
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    return handler


def setup_logging(
    *,
    rich_enabled: bool | None = None,
    json_enabled: bool | None = None,
    level: str | int | None = None,
) -> None:
    if rich_enabled is None:
        rich_enabled = os.getenv("LOG_RICH", "true").lower() == "true"
    if json_enabled is None:
        json_enabled = os.getenv("LOG_JSON", "true").lower() == "true"
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")

    if isinstance(level, str):
        numeric_level = getattr(logging, level.upper(), logging.INFO)
    else:
        numeric_level = int(level)

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False, key="ts"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _default_field_enricher,
        _sanitize_fields,
        _event_to_message,
    ]

    structlog.configure(
        processors=processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=numeric_level)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(numeric_level)

    foreign_pre_chain: list[Processor] = list(processors)

    if rich_enabled:
        console_handler = _create_rich_handler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                foreign_pre_chain=foreign_pre_chain,
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    _console_renderer,
                ],
            )
        )
        root_logger.addHandler(console_handler)

    if json_enabled:
        file_handler = _create_file_handler(Path("logs"))
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                foreign_pre_chain=foreign_pre_chain,
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    _json_renderer,
                ],
            )
        )
        root_logger.addHandler(file_handler)

    structlog.configure(
        processors=processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


__all__ = ["setup_logging", "get_logger", "json_dumps"]
