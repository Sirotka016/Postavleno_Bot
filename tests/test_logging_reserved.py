import structlog
from structlog.testing import capture_logs

from postavleno_bot.core.logging import _sanitize_fields, setup_logging


def test_logging_reserved_key() -> None:
    setup_logging(rich_enabled=False, json_enabled=False)

    logger = structlog.get_logger("test")
    logger.info("hello", result="ok")

    with capture_logs() as captured:
        logger.info("hello", result="ok")

    assert captured
    sanitized = _sanitize_fields(logger, "", dict(captured[0]))
    assert sanitized["outcome"] == "ok"
    assert "result" not in sanitized
