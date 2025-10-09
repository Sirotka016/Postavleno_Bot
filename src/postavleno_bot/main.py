from __future__ import annotations

import asyncio
import os

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

    logger = get_logger(__name__).bind(action="run")
    if os.getenv("POSTAVLENO_BOT_SKIP_POLLING") == "1":
        logger.info("Запуск бота пропущен по переменной окружения")
        return

    bot = create_bot(settings)
    dispatcher = create_dispatcher()

    logger.info("Бот запускается")

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
