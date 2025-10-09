from __future__ import annotations

import asyncio

from .app import create_bot, create_dispatcher
from .core.config import get_settings
from .core.logging import get_logger, setup_logging


async def main() -> None:
    settings = get_settings()
    setup_logging(
        rich_enabled=settings.log_rich,
        json_enabled=settings.log_json,
        level=settings.log_level,
    )

    bot = create_bot(settings)
    dispatcher = create_dispatcher()

    logger = get_logger(__name__).bind(action="run")
    logger.info("Бот запускается")

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
